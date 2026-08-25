import argparse
import sys
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
from rich.table import Table

from config import DEFAULT_TTS_URL, DEFAULT_CHUNK_LENGTH, DEFAULT_PAUSE_DURATION, DEFAULT_AUDIO_FORMAT
from extractor import DocumentExtractor
from stress_dict import StressDictionary
from voice_manager import VoiceManager
from tts_client import FishAudioClient
from pipeline import TextToSpeechPipeline, PipelineProgress
from audio_merger import AudioMerger

console = Console()

def cmd_check():
    """Checks dependencies, Fish Audio S2 connection, and voice references."""
    console.print("\n[bold cyan]=== Проверка системного окружения ===[/bold cyan]\n")
    
    # 1. FFmpeg
    import subprocess
    try:
        res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        console.print("[green]✓[/green] FFmpeg установлен")
    except Exception:
        console.print("[red]✕[/red] FFmpeg не найден в PATH!")

    # 2. Fish Audio
    client = FishAudioClient()
    if client.check_connection():
        console.print(f"[green]✓[/green] Fish Audio S2 сервер доступен ([bold]{client.api_url}[/bold])")
    else:
        console.print(f"[yellow]![/yellow] Fish Audio S2 недоступен по адресу: {client.api_url}")
        console.print("  Запустите локальный сервер: [cyan]python3 -m fish_audio.api --port 8020[/cyan]")

    # 3. Voices & Dictionary
    vm = VoiceManager()
    voices = vm.list_voices()
    console.print(f"[green]✓[/green] Загружено голосовых профилей: [bold]{len(voices)}[/bold]")
    for v in voices:
        status = "[green]OK[/green]" if v.audio_path.exists() else "[red]файл не найден[/red]"
        console.print(f"   • {v.name} -> {v.audio_path.name} ({status})")

    d = StressDictionary()
    console.print(f"[green]✓[/green] Словарь ударений содержит [bold]{len(d.entries)}[/bold] слов\n")

def cmd_convert(args):
    """Converts a PDF, TXT or raw text into an audio file."""
    input_path = Path(args.input)
    if not input_path.exists():
        console.print(f"[red]Файл не найден: {args.input}[/red]")
        sys.exit(1)

    console.print(f"\n[bold green]Начало обработки файла:[/bold green] {input_path.name}")
    
    dict_mgr = StressDictionary()
    voice_mgr = VoiceManager()
    tts_client = FishAudioClient(api_url=args.api_url)
    pipeline = TextToSpeechPipeline(dict_mgr, voice_mgr, tts_client)

    raw_text, stressed_text, chunks = pipeline.prepare_text(input_path, max_chunk_len=args.chunk_length)
    console.print(f"Извлечено символов: [bold]{len(raw_text)}[/bold] | Сформировано чанков: [bold]{len(chunks)}[/bold]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console
    ) as progress_bar:
        task = progress_bar.add_task("Синтез аудио...", total=len(chunks))

        def on_progress(p: PipelineProgress):
            progress_bar.update(task, completed=p.current_chunk, description=p.message)

        custom_params = {
            "speed": args.speed,
            "temperature": args.temperature,
            "instruct": args.instruct
        }

        output_name = args.output or input_path.stem
        out_file = pipeline.process(
            text_or_chunks=chunks,
            voice_name=args.voice,
            output_name=output_name,
            output_format=args.format,
            max_chunk_len=args.chunk_length,
            pause_duration=args.pause,
            apply_loudnorm=not args.no_loudnorm,
            custom_tts_params=custom_params,
            progress_callback=on_progress
        )

    console.print(f"\n[bold green]✓ Готово![/bold green] Аудиофайл успешно сохранен:\n[bold cyan]{out_file.resolve()}[/bold cyan]\n")

def cmd_server(args):
    """Starts the FastAPI Web Studio server."""
    import uvicorn
    console.print(f"\n[bold green]🚀 Запуск веб-студии на[/bold green] [bold cyan]http://{args.host}:{args.port}[/bold cyan]\n")
    uvicorn.run("server:app", host=args.host, port=args.port, reload=args.reload)

def main():
    parser = argparse.ArgumentParser(description="AudioBook Studio — Fish Audio S2 TTS Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Check
    subparsers.add_parser("check", help="Проверить окружение, зависимости и статус Fish Audio S2")

    # Server
    p_server = subparsers.add_parser("server", help="Запустить Web UI студию")
    p_server.add_argument("--host", default="127.0.0.1", help="Хост (по умолчанию 127.0.0.1)")
    p_server.add_argument("--port", type=int, default=8088, help="Порт (по умолчанию 8088)")
    p_server.add_argument("--reload", action="store_true", help="Авто-перезагрузка при изменении кода")

    # Convert
    p_conv = subparsers.add_parser("convert", help="Озвучить PDF/TXT файл из консоли")
    p_conv.add_argument("input", help="Путь к файлу PDF или TXT")
    p_conv.add_argument("--output", "-o", help="Имя итогового файла (без расширения)")
    p_conv.add_argument("--voice", default="default", help="Имя голосового профиля")
    p_conv.add_argument("--format", default="wav", choices=["wav", "mp3", "m4b"], help="Формат итогового аудио")
    p_conv.add_argument("--chunk-length", type=int, default=DEFAULT_CHUNK_LENGTH, help="Максимальная длина чанка")
    p_conv.add_argument("--pause", type=float, default=DEFAULT_PAUSE_DURATION, help="Длительность паузы между чанками в сек")
    p_conv.add_argument("--speed", type=float, default=1.0, help="Скорость речи")
    p_conv.add_argument("--temperature", type=float, default=0.85, help="Температура генерации")
    p_conv.add_argument("--instruct", default="Read expressively like a professional audiobook narrator. Strictly pronounce Russian 'е' as 'Е' and 'ё' as 'Ё'.", help="Инструкция интонации")
    p_conv.add_argument("--no-loudnorm", action="store_true", help="Отключить нормализацию громкости FFmpeg loudnorm")
    p_conv.add_argument("--api-url", default=DEFAULT_TTS_URL, help="URL API Fish Audio S2")

    args = parser.parse_args()

    if args.command == "check":
        cmd_check()
    elif args.command == "convert":
        cmd_convert(args)
    elif args.command == "server":
        cmd_server(args)

if __name__ == "__main__":
    main()
