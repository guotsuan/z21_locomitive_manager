"""Structured OCR with Apple Vision as the preferred macOS engine."""

from dataclasses import dataclass
import json
import platform
from pathlib import Path
import subprocess
import tempfile
import time
from typing import List, Optional, Sequence, Tuple

from .native_build import NativeBuildError, compile_swift


DEFAULT_LANGUAGES = ("de-DE", "en-US", "fr-FR")
RAILWAY_CUSTOM_WORDS = (
    "DCC", "RailCom", "RailComPlus", "PluX12", "PluX16", "PluX22",
    "NEM 651", "NEM 652", "Next18", "MTC21", "SUSI",
    "Roco", "Fleischmann", "Märklin", "Trix", "PIKO", "ESU", "ZIMO",
    "Lenz", "Brawa", "Tillig", "Arnold", "Liliput", "Bachmann",
    "Jouef", "Rivarossi", "Electrotren", "NMJ", "LS Models",
    "Spitzenlicht", "Schlusslicht", "Führerstand",
    "Führerstandsbeleuchtung", "Maschinenraumbeleuchtung", "Rangiergang",
    "Rangierlicht", "Fernlicht", "Innenbeleuchtung", "Fahrgeräusch",
    "Signalhorn", "Pfeife", "Kupplung", "Telex", "Pantograph",
    "Rauchgenerator", "Bremsenquietschen", "Bahnhofsdurchsage",
    "Schaffnerpfiff", "headlight", "tail light", "cab light",
    "shunting mode", "high beam", "interior light", "engine sound",
    "horn", "whistle", "coupler", "smoke generator", "brake squeal",
    "feux avant", "feux arrière", "éclairage cabine", "mode manœuvre",
    *tuple(f"F{number}" for number in range(33)),
)


class OCRError(RuntimeError):
    """Raised when every available OCR engine fails."""


class OCRCancelledError(OCRError):
    """Raised when the caller cancels an OCR operation."""


@dataclass(frozen=True)
class BoundingBox:
    """Normalized Vision coordinates, with an origin at bottom-left."""

    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class TextCandidate:
    text: str
    confidence: float


@dataclass(frozen=True)
class TextObservation:
    text: str
    confidence: float
    bounding_box: Optional[BoundingBox]
    candidates: Tuple[TextCandidate, ...]


@dataclass(frozen=True)
class OCRPage:
    index: int
    width: float
    height: float
    observations: Tuple[TextObservation, ...]

    @property
    def text(self) -> str:
        positioned = [item for item in self.observations
                      if item.bounding_box is not None]
        unpositioned = [item for item in self.observations
                        if item.bounding_box is None]
        positioned.sort(key=lambda item: (
            -(item.bounding_box.y + item.bounding_box.height / 2),
            item.bounding_box.x,
        ))
        return "\n".join(item.text for item in positioned + unpositioned)


@dataclass(frozen=True)
class OCRResult:
    engine: str
    languages: Tuple[str, ...]
    pages: Tuple[OCRPage, ...]

    @property
    def text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text)

    @property
    def average_confidence(self) -> Optional[float]:
        values = [item.confidence for page in self.pages
                  for item in page.observations]
        return sum(values) / len(values) if values else None


class AppleVisionOCRService:
    """Run VNRecognizeTextRequest through a small native Swift helper."""

    def __init__(self, source_path: Optional[Path] = None,
                 cache_directory: Optional[Path] = None,
                 languages: Sequence[str] = DEFAULT_LANGUAGES,
                 custom_words: Sequence[str] = RAILWAY_CUSTOM_WORDS):
        self.source_path = source_path or (
            Path(__file__).resolve().parent / "native" /
            "vision_ocr_helper.swift")
        self.cache_directory = cache_directory or (
            Path.home() / "Library" / "Caches" /
            "z21-locomotive-manager" / "vision-ocr")
        self.binary_path = self.cache_directory / "vision-ocr-helper"
        self.languages = tuple(languages)
        self.custom_words = tuple(custom_words)

    def recognize(self, input_path: Path, cancel_event=None) -> OCRResult:
        input_path = Path(input_path)
        if not input_path.is_file():
            raise OCRError(f"OCR input file does not exist: {input_path}")
        helper = self._ensure_helper()
        with tempfile.TemporaryDirectory(prefix="z21lm-vision-ocr-") as temp:
            temp_path = Path(temp)
            config_path = temp_path / "config.json"
            result_path = temp_path / "result.json"
            config_path.write_text(json.dumps({
                "languages": self.languages,
                "customWords": self.custom_words,
            }, ensure_ascii=False), encoding="utf-8")
            command = [
                str(helper), "--input", str(input_path),
                "--config", str(config_path),
                "--output", str(result_path),
            ]
            if cancel_event is None:
                process = subprocess.run(command, capture_output=True,
                                         text=True, check=False)
                stderr_text = process.stderr
            else:
                process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, text=True)
                while process.poll() is None:
                    if cancel_event.is_set():
                        process.terminate()
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                        raise OCRCancelledError("OCR was cancelled.")
                    time.sleep(0.05)
                _stdout, stderr_text = process.communicate()
            if process.returncode != 0:
                raise OCRError(
                    stderr_text.strip() or
                    "Apple Vision OCR helper exited without a result.")
            try:
                payload = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise OCRError(
                    f"Apple Vision returned an invalid result: {error}") from error
        return self._parse_result(payload)

    def _ensure_helper(self) -> Path:
        if not self.source_path.is_file():
            raise OCRError(f"Vision OCR helper source is missing: {self.source_path}")
        if (self.binary_path.is_file() and
                self.binary_path.stat().st_mtime >=
                self.source_path.stat().st_mtime):
            return self.binary_path
        self.cache_directory.mkdir(parents=True, exist_ok=True)
        temporary_binary = self.cache_directory / "helper.building"
        try:
            compile_swift(
                self.source_path,
                temporary_binary,
                self.cache_directory / "module-cache",
                frameworks=("AppKit", "Vision", "PDFKit"),
            )
        except NativeBuildError as error:
            raise OCRError(f"Unable to build Apple Vision OCR helper.\n\n{error}") from error
        temporary_binary.replace(self.binary_path)
        self.binary_path.chmod(0o755)
        return self.binary_path

    def _parse_result(self, payload) -> OCRResult:
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            message = payload.get("message") if isinstance(payload, dict) else None
            raise OCRError(message or "Apple Vision OCR failed.")
        pages: List[OCRPage] = []
        for raw_page in payload.get("pages", []):
            observations: List[TextObservation] = []
            for raw_item in raw_page.get("observations", []):
                raw_box = raw_item.get("boundingBox")
                box = None
                if isinstance(raw_box, dict):
                    box = BoundingBox(
                        x=float(raw_box["x"]), y=float(raw_box["y"]),
                        width=float(raw_box["width"]),
                        height=float(raw_box["height"]),
                    )
                candidates = tuple(TextCandidate(
                    text=str(candidate.get("text", "")),
                    confidence=float(candidate.get("confidence", 0.0)),
                ) for candidate in raw_item.get("candidates", []))
                observations.append(TextObservation(
                    text=str(raw_item.get("text", "")),
                    confidence=float(raw_item.get("confidence", 0.0)),
                    bounding_box=box,
                    candidates=candidates,
                ))
            pages.append(OCRPage(
                index=int(raw_page.get("index", len(pages))),
                width=float(raw_page.get("width", 0.0)),
                height=float(raw_page.get("height", 0.0)),
                observations=tuple(observations),
            ))
        return OCRResult(
            engine="apple-vision",
            languages=tuple(payload.get("languages", self.languages)),
            pages=tuple(pages),
        )


class TesseractOCRService:
    """Compatibility fallback for systems where Apple Vision is unavailable."""

    def recognize(self, input_path: Path, cancel_event=None) -> OCRResult:
        try:
            import pytesseract
            from PIL import Image
        except ImportError as error:
            raise OCRError("pytesseract and Pillow are required for OCR fallback.") from error

        input_path = Path(input_path)
        try:
            if input_path.suffix.lower() == ".pdf":
                from pdf2image import convert_from_path
                images = convert_from_path(str(input_path))
            else:
                images = [Image.open(str(input_path))]
            pages = []
            for index, image in enumerate(images):
                if cancel_event is not None and cancel_event.is_set():
                    raise OCRCancelledError("OCR was cancelled.")
                pages.append(OCRPage(
                    index=index,
                    width=float(image.width),
                    height=float(image.height),
                    observations=(TextObservation(
                        text=pytesseract.image_to_string(image) or "",
                        confidence=0.0,
                        bounding_box=None,
                        candidates=(),
                    ),),
                ))
            return OCRResult(engine="tesseract", languages=(),
                             pages=tuple(pages))
        except OCRCancelledError:
            raise
        except Exception as error:
            raise OCRError(f"Tesseract OCR failed: {error}") from error


class OCRService:
    """Prefer Apple Vision on macOS and fall back to Tesseract."""

    def __init__(self, vision_service=None, fallback_service=None,
                 system_name: Optional[str] = None):
        self.vision_service = vision_service or AppleVisionOCRService()
        self.fallback_service = fallback_service or TesseractOCRService()
        self.system_name = system_name or platform.system()

    def recognize(self, input_path: Path, cancel_event=None) -> OCRResult:
        vision_error = None
        if self.system_name == "Darwin":
            try:
                if cancel_event is None:
                    return self.vision_service.recognize(input_path)
                return self.vision_service.recognize(
                    input_path, cancel_event=cancel_event)
            except OCRCancelledError:
                raise
            except OCRError as error:
                vision_error = error
        try:
            if cancel_event is None:
                return self.fallback_service.recognize(input_path)
            return self.fallback_service.recognize(
                input_path, cancel_event=cancel_event)
        except OCRCancelledError:
            raise
        except OCRError as fallback_error:
            if vision_error:
                raise OCRError(
                    "Apple Vision failed: " + str(vision_error) +
                    "\n\nFallback failed: " + str(fallback_error)) from fallback_error
            raise
