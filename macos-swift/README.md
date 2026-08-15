# Z21 Locomotive Manager for macOS

这是原 Python 程序的原生 macOS Swift 重写，使用 SwiftUI + AppKit，并保留 Z21 SQLite/ZIP 格式兼容性。

## 功能

- 读取、搜索、新建、编辑、删除并原子写回 `.z21` 机车库
- 编辑全部机车资料、类别、牵引级和 F0–F127 功能卡
- 保留 Z21 包内未知文件和未识别的 SQLite 表/字段
- 导入/导出 `.z21loco`，导出后可直接 AirDrop
- 导入机车资料 JSON 和功能表 JSON
- 从本地 PDF/图片或 iPhone Continuity Camera 获取手册
- Apple Vision 本地 OCR，保留页面、置信度与坐标
- DeepSeek 字段建议和 F0–F32 功能表重建，应用前逐项审核
- DeepSeek 密钥保存在 macOS Keychain
- 自动发现仓库 `icons/` 中的所有 PNG 图标

## 构建与运行

要求 macOS 14+ 和 Xcode 26（或兼容的 Swift/Xcode 工具链）。

```bash
cd macos-swift
./build-app.sh
open "dist/Z21 Locomotive Manager.app"
```

开发运行：

```bash
cd macos-swift
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
CLANG_MODULE_CACHE_PATH="$PWD/.build/ModuleCache" \
/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/swift \
run --disable-sandbox Z21Manager ../z21_new.z21
```

测试：

```bash
cd macos-swift
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
CLANG_MODULE_CACHE_PATH="$PWD/.build/ModuleCache" \
/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/swift \
test --disable-sandbox --cache-path "$PWD/.build/cache"
```

本机 `/usr/bin/swift` 与 Command Line Tools SDK 如果版本不一致，请使用上面 Xcode App 内的工具链。
