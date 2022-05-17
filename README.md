# syosetu-epub

This is yet another syosetu to epub downloader/converter. The script rate-limit to 1 second per chapter to not get
banned.  The output epub has vertical writing

syosetuからEPUBで保存するためのスクリプトです。バンされないため1章ごとに1秒間かかります。縦書きEPUBを出力します。

## Prerequisites

    pip install beautifulsoup4 pillow jaconv

## Usage

    python3 main.py <syosetu_url> <output.epub>
