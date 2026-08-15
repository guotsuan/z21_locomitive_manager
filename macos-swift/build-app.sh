#!/bin/zsh
set -euo pipefail

script_dir="${0:A:h}"
project_root="${script_dir:h}"
developer_path="/Applications/Xcode.app/Contents/Developer"
swift_binary="${developer_path}/Toolchains/XcodeDefault.xctoolchain/usr/bin/swift"
cache_path="${script_dir}/.build/cache"
module_cache_path="${script_dir}/.build/ModuleCache"
asset_catalog_path="${script_dir}/Resources/Assets.xcassets"
asset_output_path="${script_dir}/.build/asset-catalog"
app_path="${script_dir}/dist/Z21 Locomotive Manager.app"

if [[ ! -x "${swift_binary}" ]]; then
    swift_binary="$(command -v swift)"
    developer_path="$(xcode-select -p)"
fi

DEVELOPER_DIR="${developer_path}" CLANG_MODULE_CACHE_PATH="${module_cache_path}" \
    "${swift_binary}" build --configuration release --disable-sandbox \
    --cache-path "${cache_path}"

mkdir -p "${asset_output_path}"
DEVELOPER_DIR="${developer_path}" xcrun actool "${asset_catalog_path}" \
    --compile "${asset_output_path}" \
    --platform macosx \
    --minimum-deployment-target 14.0 \
    --app-icon AppIcon \
    --output-partial-info-plist "${asset_output_path}/partial-info.plist" \
    --warnings --notices

mkdir -p "${app_path}/Contents/MacOS" "${app_path}/Contents/Resources/icons"
cp "${script_dir}/.build/release/Z21Manager" "${app_path}/Contents/MacOS/Z21Manager"
cp "${script_dir}/Info.plist" "${app_path}/Contents/Info.plist"
cp "${asset_output_path}/AppIcon.icns" "${app_path}/Contents/Resources/AppIcon.icns"
cp "${asset_output_path}/Assets.car" "${app_path}/Contents/Resources/Assets.car"
cp "${project_root}/icons/"*.png "${app_path}/Contents/Resources/icons/"
codesign --force --deep --sign - "${app_path}"

echo "Built ${app_path}"
