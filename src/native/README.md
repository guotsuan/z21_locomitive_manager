# Continuity Camera helper

This AppKit helper is built on demand as a signed `.app` bundle. It registers an
explicit services responder and a menu item with
`NSMenuItem.importFromDeviceIdentifier`, allowing AppKit to populate the
available iPhone photo and document-scanning actions. Captured pasteboard data
is written to the requested output directory, and completion is communicated
through an atomic JSON result file.

Apple requires the user to choose the device action from the system-generated
menu. The helper opens that menu automatically and also provides a button and a
clickable capture area to reopen it.

Both devices must use the same Apple Account with two-factor authentication,
and have Wi-Fi and Bluetooth enabled. If the helper cannot be built, update
Xcode Command Line Tools; importing an existing image remains available.

`vision_ocr_helper.swift` uses `VNRecognizeTextRequest` in accurate mode with
language correction, automatic language detection, prioritized recognition
languages, and a railway-specific custom dictionary. It renders PDF pages with
PDFKit and returns JSON containing up to three candidates, confidence values,
and normalized bounding boxes for every observation.
