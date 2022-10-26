import urllib.request
import bs4
import datetime
import time
import zipfile
import uuid
import os
import jaconv
import re
import locale
from PIL import Image, ImageDraw, ImageFont


JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')
locale.setlocale(locale.LC_CTYPE, "Japanese_Japan.932")


class EPUB:
    def __init__(self, url, title, author, publisher, publication_date, language='en', vertical=False):
        self.url = url
        self.title = title
        self.author = author
        self.publisher = publisher
        self.publication_date = publication_date
        self.language = language
        self.vertical = vertical

        self.cover = False

        self.uuid = str(uuid.uuid4())

        self.files = {}
        self.toc = []

    def addPage(self, filename, title, content, toc=True):
        self.toc.append((title if toc else False, 'Text/' + filename))
        self.files['Text/' + filename] = self._makePageHTML(title, content).encode('utf-8')

    def addAutoTOC(self, title='Table of Contents'):
        self.toc.append((title, '!AUTO-TOC'))

    def _makePageHTML(self, title, content):

        html = '<?xml version="1.0" encoding="UTF-8"?>\n'
        html += '<!DOCTYPE html>\n'
        html += '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="' + self.language + '">\n'
        html += '<head>\n'
        html += '<title>' + title + '</title>\n'
        html += '<link rel="stylesheet" type="text/css" href="../Styles/stylesheet.css" />\n'
        html += '</head>\n'
        html += '<body>\n'
        html += '<h1>' + title + '</h1>\n'
        html += content
        html += '</body>\n'
        html += '</html>\n'

        return html

    def setStylesheet(self, str):
        self.files['Styles/stylesheet.css'] = str

    def setDefaultStylesheet(self):
        css = '@charset "utf-8";\n'

        if self.vertical:
            css += '''            
html
{
-epub-writing-mode: vertical-rl;
writing-mode: vertical-rl;
}
'''
        else:
            css += '''
h1
{
text-align:center;
}
'''

        css += '''
body
{
text-align: left;
line-height: 1.2;
}

h1
{
margin-top: 1em;
margin-bottom: 2em;
font-size: 1.5em;
font-weight: bold;
page-break-before: always;
}

p
{
margin: 0;
text-align: justify;
}

p.first-para
{
text-indent: 0;
}

p.seperator
{
text-indent: 0;
text-align: center;
margin: 1.5em 0;
}

hr
{
margin: 1.5em 0;
}

.toc-list
{
list-style: none;
}

.toc-item
{
margin-left: 0.5em;
margin-top: 0.5em;
margin-bottom: 0.5em;
text-ident: 0;
}
        '''

        self.setStylesheet(css)

    def _makeTOC(self):
        auto_toc = False
        title = ''
        for idx, toc in enumerate(self.toc):
            if toc[1] == '!AUTO-TOC':
                auto_toc = True
                title = toc[0]
                self.toc[idx] = (toc[0], 'Text/toc.xhtml')
        if not auto_toc:
            return

        toc_html = '<?xml version="1.0" encoding="UTF-8"?>\n'
        toc_html += '<!DOCTYPE html>\n'
        toc_html += '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="' + self.language + '" xmlns:epub="http://www.idpf.org/2007/ops">\n'
        toc_html += '<head>\n'
        toc_html += '<title>' + title + '</title>\n'
        toc_html += '<link rel="stylesheet" type="text/css" href="../Styles/stylesheet.css" />\n'
        toc_html += '</head>\n'
        toc_html += '<body>\n'
        toc_html += '<h1>' + title + '</h1>\n'
        toc_html += '<nav epub:type="toc">\n'
        toc_html += '<ol class="toc-list">\n'
        for title, filename in self.toc:
            if not title:
                continue
            toc_html += '<li class="toc-item">\n'
            toc_html += '<a href="' + os.path.basename(filename) + '">' + title + '</a>\n'
            toc_html += '</li>\n'
        toc_html += '</ol>\n'
        toc_html += '</nav>\n'
        toc_html += '</body>\n'
        toc_html += '</html>\n'

        self.files['Text/toc.xhtml'] = toc_html


    def _mediaType(self, filename):
        if filename.endswith('.ncx'):
            return 'application/x-dtbncx+xml'
        elif filename.endswith('.opf'):
            return 'application/oebps-package+xml'
        elif filename.endswith('.xhtml') or filename.endswith('.html'):
            return 'application/xhtml+xml'
        elif filename.endswith('.css'):
            return 'text/css'
        elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
            return 'image/jpeg'
        elif filename.endswith('.png'):
            return 'image/png'
        elif filename.endswith('.gif'):
            return 'image/gif'
        elif filename.endswith('.svg'):
            return 'image/svg+xml'
        elif filename.endswith('.ttf'):
            return 'application/x-font-ttf'
        elif filename.endswith('.otf'):
            return 'application/x-font-opentype'
        else:
            raise Exception('Unknown media type for file ' + filename)

    def _makeID(self, filename):
        if filename == 'toc.ncx':
            return 'ncx'
        return filename.replace('/', '_').replace('.', '_')

    def _makeItemProperties(self, item):
        if item == 'Text/toc.xhtml':
            return ' properties="nav"'
        if item == 'Images/cover.png':
            return ' properties="cover-image"'
        if item[-5:] == 'xhtml' and '<svg' in self.files[item].decode('utf-8'):
            return ' properties="svg"'
        return ""


    def makeOPF(self):
        self.opf = '<?xml version="1.0" encoding="UTF-8"?>\n'
        self.opf += '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="BookId">\n'
        self.opf += '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">\n'
        self.opf += '<dc:title>' + self.title + '</dc:title>\n'
        self.opf += '<meta property="role" refines="#author" scheme="marc:relators">aut</meta>'
        self.opf += '<dc:creator id="author">' + self.author + '</dc:creator>\n'
        self.opf += '<dc:date>' + datetime.datetime.strftime(datetime.datetime.fromtimestamp(self.publication_date), '%Y-%m-%d') + 'T15:00:00Z</dc:date>\n'
        self.opf += '<meta property="dcterms:modified">' + datetime.datetime.strftime(datetime.datetime.fromtimestamp(self.publication_date), '%Y-%m-%d') + 'T15:00:00Z</meta>\n'
        self.opf += '<dc:identifier id="BookId">urn:uuid:' + self.uuid + '</dc:identifier>\n'
        self.opf += '<dc:language>' + self.language + '</dc:language>\n'
        self.opf += '<dc:publisher>' + self.publisher + '</dc:publisher>\n'
        self.opf += '<dc:source>' + self.url + '</dc:source>\n'
        self.opf += '<dc:identifier id="source-id">url:' + self.url + '</dc:identifier>\n'
        if self.cover:
            self.opf += '<meta name="cover" content="' + self._makeID(self.cover) + '"/>\n'
        self.opf += '</metadata>\n'
        self.opf += '<manifest>\n'
        for file in self.files.keys():
            properties = self._makeItemProperties(file)
            self.opf += '<item id="' + self._makeID(file) + '" href="' + file + '" media-type="' + self._mediaType(file) + '"' + properties + '/>\n'
        self.opf += '</manifest>\n'
        if self.vertical:
            self.opf += '<spine toc="ncx" page-progression-direction="rtl">\n'
        else:
            self.opf += '<spine toc="ncx">\n'
        for file in self.toc:
            self.opf += '<itemref idref="' + self._makeID(file[1]) + '"/>\n'
        self.opf += '</spine>\n'
        self.opf += '</package>\n'

        self.files['content.opf'] = self.opf.encode('utf-8')

    def makeNCX(self):
        self.ncx = '<?xml version="1.0" encoding="UTF-8"?>\n'
        # self.ncx += '<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">\n'
        self.ncx += '<ncx xml:lang="en" xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">\n'
        self.ncx += '<head>\n'
        self.ncx += '<meta name="dtb:uid" content="urn:uuid:' + self.uuid + '"/>\n'
        self.ncx += '<meta name="dtb:depth" content="1"/>\n'
        self.ncx += '<meta name="dtb:totalPageCount" content="0"/>\n'
        self.ncx += '<meta name="dtb:maxPageNumber" content="0"/>\n'
        self.ncx += '</head>\n'
        self.ncx += '<docTitle>\n'
        self.ncx += '<text>' + self.title + '</text>\n'
        self.ncx += '</docTitle>\n'
        self.ncx += '<navMap>\n'
        order = 1
        for file in self.toc:
            if not file[0]:
                continue

            self.ncx += '<navPoint class="chapter" id="' + self._makeID(file[1]) + '" playOrder="' + str(order) + '">\n'
            self.ncx += '<navLabel>\n'
            self.ncx += '<text>' + file[0] + '</text>\n'
            self.ncx += '</navLabel>\n'
            self.ncx += '<content src="' + file[1] + '"/>\n'
            self.ncx += '</navPoint>\n'

            order += 1

        self.ncx += '</navMap>\n'
        self.ncx += '</ncx>\n'

        self.files['toc.ncx'] = self.ncx.encode('utf-8')

    def generateCover(self):
        from PIL import Image
        from io import BytesIO
        import urllib.parse
        cover_img = Image.new('RGB', (1875, 2500), (61, 64, 112))
        with urllib.request.urlopen('http://placehold.jp/120/3d4070/ffffff/1875x1875.png?text={}'.format(urllib.parse.quote(self.title))) as f:
            cover_img.paste(Image.open(BytesIO(f.read())), (0, 0))
        with urllib.request.urlopen('http://placehold.jp/100/3d4070/ffffff/1875x625.png?text={}'.format(urllib.parse.quote(self.author))) as f:
            cover_img.paste(Image.open(BytesIO(f.read())), (0, 1875))
        img_byte_arr = BytesIO()
        cover_img.save(img_byte_arr, format='PNG')
        self.files['Images/cover.png'] = img_byte_arr.getvalue()
        self.cover = 'Images/cover.png'

        self.files['Text/cover.xhtml'] = '''<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>Cover</title>
</head>
<body>
  <div style="text-align: center; padding: 0pt; margin: 0pt;">
    <svg xmlns="http://www.w3.org/2000/svg" height="100%" preserveAspectRatio="xMidYMid meet" version="1.1" viewBox="0 0 1875 2500" width="100%" xmlns:xlink="http://www.w3.org/1999/xlink">
      <image width="1875" height="2500" xlink:href="../Images/cover.png"/>
    </svg>
  </div>
</body>
</html>
'''.encode('utf-8')
        self.toc.insert(0, (False, 'Text/cover.xhtml'))

    def createContainer(self):
        self.container = '<?xml version="1.0" encoding="UTF-8"?>\n'
        self.container += '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        self.container += '<rootfiles>\n'
        self.container += '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>\n'
        self.container += '</rootfiles>\n'
        self.container += '</container>\n'

        return self.container.encode('utf-8')


    def makeEPUB(self, filename):
        self._makeTOC()
        self.makeNCX()
        self.makeOPF()

        epub = zipfile.ZipFile(filename, 'w')
        epub.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        epub.writestr('META-INF/container.xml', self.createContainer())
        for filename, data in self.files.items():
            epub.writestr('OEBPS/' + filename, data)
        epub.close()


def parse_long_update(long_update):
    for x in long_update.children:
        if isinstance(x, bs4.element.NavigableString):
            return datetime.datetime.strptime(x.strip(), '%Y/%m/%d %H:%M').replace(tzinfo=JST).timestamp()
    return 0


def parse_chapter(chapter_url):
    with urllib.request.urlopen(chapter_url) as response:
        html = response.read().decode('utf-8')
    soup = bs4.BeautifulSoup(html, 'html.parser')
    chapter_title = soup.find('p', class_='novel_subtitle').string
    chapter_content = parse_content(soup.find('div', id='novel_honbun'))
    time.sleep(1)
    return chapter_title, chapter_content


def parse_content(chapter_soup):
    for p in chapter_soup.find_all('p'):
        if p.string and not p.string[0] == '「' and not p.string[0] == "　":
            p.insert(0, "　")
    return chapter_soup.decode_contents()


def main(argv):
    if len(argv) != 3:
        print("Usage: main.py <url> <output.epub>")
        exit(1)
    url = argv[1]
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://ncode.syosetu.com/{}/".format(url)
    print('Fetching story from ' + url)
    with urllib.request.urlopen(url) as response:
        html = response.read().decode('utf-8')
    soup = bs4.BeautifulSoup(html, 'html.parser')
    title = soup.find('p', class_='novel_title').string
    print('Title: ' + title)
    author = soup.find('div', class_='novel_writername').a.string
    print('Author: ' + author)
    summary = soup.find('div', id='novel_ex').decode_contents()

    # Find last update date
    last_update = max(*[parse_long_update(x) for x in soup.find_all('dt', class_='long_update')])
    print("Published: {}".format(datetime.datetime.strftime(datetime.datetime.fromtimestamp(last_update), '%Y-%m-%d')))

    # Epub
    epub = EPUB(url, title, author, 'Syosetu', last_update, 'ja', True)
    epub.setDefaultStylesheet()

    # Summary
    arasuji = '''
    <p>品名：{}</p>
    <p>作者：{}</p>
    <p class="separator">&#160;</p>
    <p>{}</p>
    <p class="separator">&#160;</p>
    <p>最終更新日：{}</p>
    <p>読み取り日：{}</p>
    '''.format(title, author, summary, jaconv.h2z(datetime.datetime.strftime(datetime.datetime.fromtimestamp(last_update), '%Y年%m月%d日'), digit=True), jaconv.h2z(datetime.datetime.strftime(datetime.datetime.now(), '%Y年%m月%d日'), digit=True))
    epub.addPage('Summary.xhtml', '小説紹介', arasuji)

    epub.addAutoTOC('目次')

    # Some regexp
    remove_blank_p = re.compile(r'<p id="L\d+"><br/></p>')

    # Read table of content
    i = 0
    for chapter in soup.find_all('dl', class_='novel_sublist2'):
        i += 1

        chapter_url = chapter.find('a')['href']
        chapter_title, chapter_content = parse_chapter('https://ncode.syosetu.com{}'.format(chapter_url))

        # We will use vertical writing, so convert everything to full width
        chapter_title = jaconv.h2z(chapter_title, ascii=True, digit=True, kana=False)

        # Remove blank paragraph
        chapter_content = remove_blank_p.sub('', chapter_content)

        print('Chapter {}'.format(chapter_title))
        epub.addPage('Chapter{:05d}.xhtml'.format(i), chapter_title, chapter_content)

    epub.generateCover()
    epub.makeEPUB(argv[2])


if __name__ == "__main__":
    import sys
    main(sys.argv)
