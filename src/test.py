Appuyez
sur
Alt + i
pour
créer
un
brouillon
avec
Copilot

De: Matéo
Evan
Muller < mateo.muller @ epfl.ch >
Envoyé: Monday, 20
October
2025
10: 04
À: Yannick
Sidney
Pezeu < yannick.pezeu @ epfl.ch >
Objet: Re: Docling
Error

La
valeur
est
toujours
à
10
minutes, j’ai
rien
modifié
à
ce
niveau.

Voici
les
logs
coté
serveur:
Starting
production
server 🚀

Server
started
at
http: // 0.0
.0
.0: 8080
Documentation
at
http: // 0.0
.0
.0: 8080 / docs
Scalar
docs
at
http: // 0.0
.0
.0: 8080 / scalar
UI
at
http: // 0.0
.0
.0: 8080 / ui

Logs:
new / ui
INFO: Started
server
process[1]
INFO: Waiting
for application startup.
    INFO: Application
    startup
    complete.
INFO: Uvicorn
running
on
http: // 0.0
.0
.0: 8080(Press
CTRL + C
to
quit)
ERROR: docling.datamodel.document:Input
document
Canevas - LEX.doc
with format None does not match any allowed format: (dict_keys([ < InputFormat.DOCX
                                                     : 'docx' >, < InputFormat.PPTX: 'pptx' >, < InputFormat.HTML: 'html' >, < InputFormat.IMAGE: 'image' >, < InputFormat.PDF: 'pdf' >, < InputFormat.ASCIIDOC: 'asciidoc' >, < InputFormat.MD: 'md' >, < InputFormat.CSV: 'csv' >, < InputFormat.XLSX: 'xlsx' >, < InputFormat.XML_USPTO: 'xml_uspto' >, < InputFormat.XML_JATS: 'xml_jats' >, < InputFormat.METS_GBS: 'mets_gbs' >, < InputFormat.JSON_DOCLING: 'json_docling' >, < InputFormat.AUDIO: 'audio' >, < InputFormat.VTT: 'vtt' >]))
ERROR: docling_jobkit.orchestrators.local.worker:Worker
1
failed
to
process
job
f77051a4 - 4868 - 429
c - 9
c69 - 80
ccb8c0ff86: File
format
not allowed: Canevas - LEX.doc
WARNING: docling.backend.mspowerpoint_backend:Warning: image
cannot
be
loaded
by
Pillow: cannot
find
loader
for this WMF file
ERROR: docling.datamodel.document:Input
document
Canevas - LEX - anglais.doc
with format None does not match any allowed format: (dict_keys([ < InputFormat.DOCX
                                                     : 'docx' >, < InputFormat.PPTX: 'pptx' >, < InputFormat.HTML: 'html' >, < InputFormat.IMAGE: 'image' >, < InputFormat.PDF: 'pdf' >, < InputFormat.ASCIIDOC: 'asciidoc' >, < InputFormat.MD: 'md' >, < InputFormat.CSV: 'csv' >, < InputFormat.XLSX: 'xlsx' >, < InputFormat.XML_USPTO: 'xml_uspto' >, < InputFormat.XML_JATS: 'xml_jats' >, < InputFormat.METS_GBS: 'mets_gbs' >, < InputFormat.JSON_DOCLING: 'json_docling' >, < InputFormat.AUDIO: 'audio' >, < InputFormat.VTT: 'vtt' >]))
ERROR: docling_jobkit.orchestrators.local.worker:Worker
1
failed
to
process
job
0
c4c6966 - c35d - 4
b35 - b4e0 - f855bbb1827a: File
format
not allowed: Canevas - LEX - anglais.doc
ERROR: docling.datamodel.document:Input
document
Convention - stage - architectes.doc
with format None does not match any allowed format: (dict_keys([ < InputFormat.DOCX
                                                     : 'docx' >, < InputFormat.PPTX: 'pptx' >, < InputFormat.HTML: 'html' >, < InputFormat.IMAGE: 'image' >, < InputFormat.PDF: 'pdf' >, < InputFormat.ASCIIDOC: 'asciidoc' >, < InputFormat.MD: 'md' >, < InputFormat.CSV: 'csv' >, < InputFormat.XLSX: 'xlsx' >, < InputFormat.XML_USPTO: 'xml_uspto' >, < InputFormat.XML_JATS: 'xml_jats' >, < InputFormat.METS_GBS: 'mets_gbs' >, < InputFormat.JSON_DOCLING: 'json_docling' >, < InputFormat.AUDIO: 'audio' >, < InputFormat.VTT: 'vtt' >]))
ERROR: docling_jobkit.orchestrators.local.worker:Worker
0
failed
to
process
job
200521
bb - bb91 - 4
a87 - b32c - 1925
be9890fd: File
format
not allowed: Convention - stage - architectes.doc
ERROR: docling_jobkit.orchestrators.local.worker:Worker
0
failed
to
process
job
0
a732a11 - 7783 - 4
ad0 - 8188 - 1693060
d243b: Cannot
find
all
provided
RefItems in doc: ['#/texts/13']
ERROR: docling_jobkit.orchestrators.local.worker:Worker
1
failed
to
process
job
3
eae9827 - 7
c08 - 450
c - 9
b09 - 6397939
fa932: Cannot
find
all
provided
RefItems in doc: ['#/texts/13']
ERROR: docling.datamodel.document:Input
document
Internship - architecture - agreement.doc
with format None does not match any allowed format: (dict_keys([ < InputFormat.DOCX
                                                     : 'docx' >, < InputFormat.PPTX: 'pptx' >, < InputFormat.HTML: 'html' >, < InputFormat.IMAGE: 'image' >, < InputFormat.PDF: 'pdf' >, < InputFormat.ASCIIDOC: 'asciidoc' >, < InputFormat.MD: 'md' >, < InputFormat.CSV: 'csv' >, < InputFormat.XLSX: 'xlsx' >, < InputFormat.XML_USPTO: 'xml_uspto' >, < InputFormat.XML_JATS: 'xml_jats' >, < InputFormat.METS_GBS: 'mets_gbs' >, < InputFormat.JSON_DOCLING: 'json_docling' >, < InputFormat.AUDIO: 'audio' >, < InputFormat.VTT: 'vtt' >]))
ERROR: docling_jobkit.orchestrators.local.worker:Worker
1
failed
to
process
job
1
c485f20 - 45
b7 - 4
f22 - 8154 - 36
fcc5c24ab0: File
format
not allowed: Internship - architecture - agreement.doc
ERROR: docling_jobkit.orchestrators.local.worker:Worker
1
failed
to
process
job
89
dc349d - 0
a1f - 4
a8a - a461 - b61bbb5f01a2: Cannot
find
all
provided
RefItems in doc: ['#/texts/13']
ERROR: docling_jobkit.orchestrators.local.worker:Worker
0
failed
to
process
job
4e5
f5a38 - e91e - 401
e - ae8f - 9
f6dea1b05d1: Cannot
find
all
provided
RefItems in doc: ['#/texts/15']
ERROR: docling.datamodel.document:An
unexpected
error
occurred
while opening the document Brochure-en-Fran_C3_A7ais.pdf
Traceback(most
recent
call
last):
File
"/opt/app-root/lib64/python3.12/site-packages/docling/datamodel/document.py", line
152, in __init__
self._init_doc(backend, path_or_stream)
File
"/opt/app-root/lib64/python3.12/site-packages/docling/datamodel/document.py", line
188, in _init_doc
self._backend = backend(self, path_or_stream=path_or_stream)
^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/docling/backend/docling_parse_v4_backend.py", line
196, in __init__
self._pdoc = pdfium.PdfDocument(self.path_or_stream)
^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/pypdfium2/_helpers/document.py", line
78, in __init__
self.raw, to_hold, to_close = _open_pdf(self._input, self._password, self._autoclose)
^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/pypdfium2/_helpers/document.py", line
678, in _open_pdf
raise PdfiumError(f"Failed to load document (PDFium: {pdfium_i.ErrorToStr.get(err_code)}).")
pypdfium2._helpers.misc.PdfiumError: Failed
to
load
document(PDFium: Data
format
error).
ERROR: docling_jobkit.orchestrators.local.worker:Worker
1
failed
to
process
job
a56b047b - c119 - 406
d - 8
dd7 - 06
a680d0b70d: Input
document
Brochure - en - Fran_C3_A7ais.pdf is not valid.
ERROR: docling.datamodel.document:An
unexpected
error
occurred
while opening the document Strategie_Climat_Durabilite_EPFL_2023.pdf
Traceback(most
recent
call
last):
File
"/opt/app-root/lib64/python3.12/site-packages/docling/datamodel/document.py", line
152, in __init__
self._init_doc(backend, path_or_stream)
File
"/opt/app-root/lib64/python3.12/site-packages/docling/datamodel/document.py", line
188, in _init_doc
self._backend = backend(self, path_or_stream=path_or_stream)
^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/docling/backend/docling_parse_v4_backend.py", line
196, in __init__
self._pdoc = pdfium.PdfDocument(self.path_or_stream)
^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/pypdfium2/_helpers/document.py", line
78, in __init__
self.raw, to_hold, to_close = _open_pdf(self._input, self._password, self._autoclose)
^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/pypdfium2/_helpers/document.py", line
678, in _open_pdf
raise PdfiumError(f"Failed to load document (PDFium: {pdfium_i.ErrorToStr.get(err_code)}).")
pypdfium2._helpers.misc.PdfiumError: Failed
to
load
document(PDFium: Data
format
error).
ERROR: docling_jobkit.orchestrators.local.worker:Worker
1
failed
to
process
job
e175c704 - dcff - 488
d - 9295 - eec5f0fc4e0f: Input
document
Strategie_Climat_Durabilite_EPFL_2023.pdf is not valid.
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=False underline=False strikethrough=False script=<Script.SUPER: '
super
'>' and 'bold=False italic=False underline=False strikethrough=False script=<Script.SUB: '
sub
'>'! Chose
'bold=False italic=False underline=False strikethrough=False script=<Script.SUB: '
sub
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=False underline=False strikethrough=False script=<Script.SUPER: '
super
'>' and 'bold=False italic=False underline=False strikethrough=False script=<Script.SUB: '
sub
'>'! Chose
'bold=False italic=False underline=False strikethrough=False script=<Script.SUB: '
sub
'>'
ERROR: docling.datamodel.document:An
unexpected
error
occurred
while opening the document leitlinien-ki_e.pdf
Traceback(most
recent
call
last):
File
"/opt/app-root/lib64/python3.12/site-packages/docling/datamodel/document.py", line
152, in __init__
self._init_doc(backend, path_or_stream)
File
"/opt/app-root/lib64/python3.12/site-packages/docling/datamodel/document.py", line
188, in _init_doc
self._backend = backend(self, path_or_stream=path_or_stream)
^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/docling/backend/docling_parse_v4_backend.py", line
196, in __init__
self._pdoc = pdfium.PdfDocument(self.path_or_stream)
^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/pypdfium2/_helpers/document.py", line
78, in __init__
self.raw, to_hold, to_close = _open_pdf(self._input, self._password, self._autoclose)
^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/pypdfium2/_helpers/document.py", line
678, in _open_pdf
raise PdfiumError(f"Failed to load document (PDFium: {pdfium_i.ErrorToStr.get(err_code)}).")
pypdfium2._helpers.misc.PdfiumError: Failed
to
load
document(PDFium: Data
format
error).
ERROR: docling_jobkit.orchestrators.local.worker:Worker
0
failed
to
process
job
70
b7b870 - ef62 - 4e60 - aff8 - ee2d33d9f90f: Input
document
leitlinien - ki_e.pdf is not valid.
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.SUPER: '
super
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.SUPER: '
super
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.SUPER: '
super
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=False italic=False underline=True strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.SUPER: '
super
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.SUPER: '
super
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.SUPER: '
super
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.SUPER: '
super
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.SUPER: '
super
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.SUPER: '
super
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.SUPER: '
super
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.SUPER: '
super
'>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
ERROR: docling.datamodel.document:Input
document
agAPEL22.zip
with format None does not match any allowed format: (dict_keys([ < InputFormat.DOCX
                                                     : 'docx' >, < InputFormat.PPTX: 'pptx' >, < InputFormat.HTML: 'html' >, < InputFormat.IMAGE: 'image' >, < InputFormat.PDF: 'pdf' >, < InputFormat.ASCIIDOC: 'asciidoc' >, < InputFormat.MD: 'md' >, < InputFormat.CSV: 'csv' >, < InputFormat.XLSX: 'xlsx' >, < InputFormat.XML_USPTO: 'xml_uspto' >, < InputFormat.XML_JATS: 'xml_jats' >, < InputFormat.METS_GBS: 'mets_gbs' >, < InputFormat.JSON_DOCLING: 'json_docling' >, < InputFormat.AUDIO: 'audio' >, < InputFormat.VTT: 'vtt' >]))
ERROR: docling_jobkit.orchestrators.local.worker:Worker
1
failed
to
process
job
1
cfea09b - edb6 - 4e70 - b27f - 14
a522c75957: File
format
not allowed: agAPEL22.zip
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
WARNING: docling.backend.html_backend:Clashing
formatting: 'bold=False italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'! Chose
'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
baseline
'>'
ERROR: docling_jobkit.orchestrators.local.worker:Worker
1
failed
to
process
job
e38b968c - 218
a - 4
cdf - a10d - f6261a079247: Cannot
find
all
provided
RefItems in doc: ['#/texts/24']
ERROR: docling.datamodel.document:An
unexpected
error
occurred
while opening the document Plan-d-action_Sant-Mentale_Enqu-te-de-satisfaction_r-sum-_EN.pptx
Traceback(most
recent
call
last):
File
"/opt/app-root/lib64/python3.12/site-packages/docling/backend/mspowerpoint_backend.py", line
50, in __init__
self.pptx_obj = Presentation(self.path_or_stream)
^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/pptx/api.py", line
31, in Presentation
presentation_part = Package.open(pptx).main_document_part
^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/pptx/opc/package.py", line
82, in open
return cls(pkg_file)._load()
^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/pptx/opc/package.py", line
160, in _load
pkg_xml_rels, parts = _PackageLoader.load(self._pkg_file, cast("Package", self))
^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/pptx/opc/package.py", line
190, in load
return cls(pkg_file, package)._load()
^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/pptx/opc/package.py", line
194, in _load
parts, xml_rels = self._parts, self._xml_rels
^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/pptx/util.py", line
191, in __get__
value = self._fget(obj)
^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/pptx/opc/package.py", line
222, in _parts
content_types = self._content_types
^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/pptx/util.py", line
191, in __get__
value = self._fget(obj)
^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/pptx/opc/package.py", line
207, in _content_types
return _ContentTypeMap.from_xml(self._package_reader[CONTENT_TYPES_URI])
~~~~~~~~~~~~~~~~~~~~ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/pptx/opc/serialized.py", line
38, in __getitem__
return self._blob_reader[pack_uri]
~~~~~~~~~~~~~~~~~ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
File
"/opt/app-root/lib64/python3.12/site-packages/pptx/opc/serialized.py", line
187, in __getitem__
if pack_uri not in self._blobs:
    ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
    File
    "/opt/app-root/lib64/python3.12/site-packages/pptx/util.py", line
    191, in __get__
    value = self._fget(obj)
    ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
    File
    "/opt/app-root/lib64/python3.12/site-packages/pptx/opc/serialized.py", line
    194, in _blobs
    with zipfile.ZipFile(self._pkg_file, "r") as z:
        ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
        File
        "/usr/lib64/python3.12/zipfile/__init__.py", line
        1354, in __init__
        self._RealGetContents()
        File
        "/usr/lib64/python3.12/zipfile/__init__.py", line
        1421, in _RealGetContents
        raise BadZipFile("File is not a zip file")
        zipfile.BadZipFile: File is not a
        zip
        file

        The
        above
        exception
        was
        the
        direct
        cause
        of
        the
        following
        exception:

        Traceback(most
        recent
        call
        last):
        File
        "/opt/app-root/lib64/python3.12/site-packages/docling/datamodel/document.py", line
        152, in __init__
        self._init_doc(backend, path_or_stream)
        File
        "/opt/app-root/lib64/python3.12/site-packages/docling/datamodel/document.py", line
        188, in _init_doc
        self._backend = backend(self, path_or_stream=path_or_stream)
        ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
        File
        "/opt/app-root/lib64/python3.12/site-packages/docling/backend/mspowerpoint_backend.py", line
        56, in __init__
        raise RuntimeError(
            RuntimeError: MsPowerpointDocumentBackend
        could
        not load
        document
        with hash 3a410b1d76e19495dd238f21cb3d3166311f2f1bb2a4f95f8908f437ce4089e7
        ERROR:docling_jobkit.orchestrators.local.worker: Worker
        0
        failed
        to
        process
        job
        69
        a50628 - 8518 - 4
        d8c - ba8b - 126
        c74a314d4: Input
        document
        Plan - d - action_Sant - Mentale_Enqu - te - de - satisfaction_r - sum - _EN.pptx is not valid.
        ERROR: docling_jobkit.orchestrators.local.worker:Worker
        1
        failed
        to
        process
        job
        25e85
        bbe - 6575 - 4611 - 94
        d9 - 704
        ed8acfe9b: Cannot
        find
        all
        provided
        RefItems in doc: ['#/texts/23']
        ERROR: docling_jobkit.orchestrators.local.worker:Worker
        1
        failed
        to
        process
        job
        922
        a456c - 94
        b1 - 4317 - a738 - c0e8ac01a963: Cannot
        find
        all
        provided
        RefItems in doc: ['#/texts/25']
        ERROR: docling.datamodel.document:Input
        document
        2.6
        .3
        .1
        .2 - 2025 - 10 - 03 - Modele_Facture_Subventions_2026.doc
        with format None does not match any allowed format: (dict_keys([ < InputFormat.DOCX
                                                             : 'docx' >, < InputFormat.PPTX: 'pptx' >, < InputFormat.HTML: 'html' >, < InputFormat.IMAGE: 'image' >, < InputFormat.PDF: 'pdf' >, < InputFormat.ASCIIDOC: 'asciidoc' >, < InputFormat.MD: 'md' >, < InputFormat.CSV: 'csv' >, < InputFormat.XLSX: 'xlsx' >, < InputFormat.XML_USPTO: 'xml_uspto' >, < InputFormat.XML_JATS: 'xml_jats' >, < InputFormat.METS_GBS: 'mets_gbs' >, < InputFormat.JSON_DOCLING: 'json_docling' >, < InputFormat.AUDIO: 'audio' >, < InputFormat.VTT: 'vtt' >]))
        ERROR: docling_jobkit.orchestrators.local.worker:Worker
        1
        failed
        to
        process
        job
        dcec61f3 - 748
        d - 4
        af2 - 91
        ea - 0
        fd4521a0642: File
        format
        not allowed: 2.6
        .3
        .1
        .2 - 2025 - 10 - 03 - Modele_Facture_Subventions_2026.doc
        WARNING: docling.backend.html_backend:Clashing
        formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
        baseline
        '>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
        baseline
        '>'! Chose
        'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
        baseline
        '>'
        WARNING: docling.backend.html_backend:Clashing
        formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
        baseline
        '>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
        baseline
        '>'! Chose
        'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
        baseline
        '>'
        WARNING: docling.backend.html_backend:Clashing
        formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
        baseline
        '>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
        baseline
        '>'! Chose
        'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
        baseline
        '>'
        WARNING: docling.backend.html_backend:Clashing
        formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
        baseline
        '>' and 'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
        baseline
        '>'! Chose
        'bold=True italic=True underline=False strikethrough=False script=<Script.BASELINE: '
        baseline
        '>'
        ERROR: docling.datamodel.document:An
        unexpected
        error
        occurred
        while opening the document La-naissance-du-got-2.pdf
        Traceback(most
        recent
        call
        last):
        File
        "/opt/app-root/lib64/python3.12/site-packages/docling/datamodel/document.py", line
        152, in __init__
        self._init_doc(backend, path_or_stream)
        File
        "/opt/app-root/lib64/python3.12/site-packages/docling/datamodel/document.py", line
        188, in _init_doc
        self._backend = backend(self, path_or_stream=path_or_stream)
        ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
        File
        "/opt/app-root/lib64/python3.12/site-packages/docling/backend/docling_parse_v4_backend.py", line
        196, in __init__
        self._pdoc = pdfium.PdfDocument(self.path_or_stream)
        ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
        File
        "/opt/app-root/lib64/python3.12/site-packages/pypdfium2/_helpers/document.py", line
        78, in __init__
        self.raw, to_hold, to_close = _open_pdf(self._input, self._password, self._autoclose)
        ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^
        File
        "/opt/app-root/lib64/python3.12/site-packages/pypdfium2/_helpers/document.py", line
        678, in _open_pdf
        raise PdfiumError(f"Failed to load document (PDFium: {pdfium_i.ErrorToStr.get(err_code)}).")
        pypdfium2._helpers.misc.PdfiumError: Failed
        to
        load
        document(PDFium: Data
        format
        error).
        ERROR: docling_jobkit.orchestrators.local.worker:Worker
        0
        failed
        to
        process
        job
        9
        bee337c - 6453 - 4
        faf - b66a - a6a8857a0ff3: Input
        document
        La - naissance - du - got - 2.
        pdf is not valid.
        ERROR: docling_jobkit.orchestrators.local.worker:Worker
        1
        failed
        to
        process
        job
        e9e68240 - f513 - 4
        a35 - b567 - 6051
        ce7c912f: maximum
        recursion
        depth
        exceeded
        WARNING: docling.backend.html_backend:Clashing
        formatting: 'bold=True italic=False underline=False strikethrough=False script=<Script.SUPER: '
        super
        '>' and 'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
        baseline
        '>'! Chose
        'bold=True italic=False underline=False strikethrough=False script=<Script.BASELINE: '
        baseline
        '>'
        ERROR: docling.datamodel.document:Input
        document
        Custom - picto - PNG.zip
        with format None does not match any allowed format: (dict_keys([ < InputFormat.DOCX
                                                             : 'docx' >, < InputFormat.PPTX: 'pptx' >, < InputFormat.HTML: 'html' >, < InputFormat.IMAGE: 'image' >, < InputFormat.PDF: 'pdf' >, < InputFormat.ASCIIDOC: 'asciidoc' >, < InputFormat.MD: 'md' >, < InputFormat.CSV: 'csv' >, < InputFormat.XLSX: 'xlsx' >, < InputFormat.XML_USPTO: 'xml_uspto' >, < InputFormat.XML_JATS: 'xml_jats' >, < InputFormat.METS_GBS: 'mets_gbs' >, < InputFormat.JSON_DOCLING: 'json_docling' >, < InputFormat.AUDIO: 'audio' >, < InputFormat.VTT: 'vtt' >]))
        ERROR: docling_jobkit.orchestrators.local.worker:Worker
        0
        failed
        to
        process
        job
        296
        be8ed - 4
        fc2 - 488
        b - 88
        fb - c7a34127275e: File
        format
        not allowed: Custom - picto - PNG.zip
        ERROR: docling.datamodel.document:Input
        document
        Emergency - picto - PNG.zip
        with format None does not match any allowed format: (dict_keys([ < InputFormat.DOCX
                                                             : 'docx' >, < InputFormat.PPTX: 'pptx' >, < InputFormat.HTML: 'html' >, < InputFormat.IMAGE: 'image' >, < InputFormat.PDF: 'pdf' >, < InputFormat.ASCIIDOC: 'asciidoc' >, < InputFormat.MD: 'md' >, < InputFormat.CSV: 'csv' >, < InputFormat.XLSX: 'xlsx' >, < InputFormat.XML_USPTO: 'xml_uspto' >, < InputFormat.XML_JATS: 'xml_jats' >, < InputFormat.METS_GBS: 'mets_gbs' >, < InputFormat.JSON_DOCLING: 'json_docling' >, < InputFormat.AUDIO: 'audio' >, < InputFormat.VTT: 'vtt' >]))
        ERROR: docling_jobkit.orchestrators.local.worker:Worker
        1
        failed
        to
        process
        job
        1
        d747c2c - 0370 - 4873 - 8
        f95 - 9
        aead5b54265: File
        format
        not allowed: Emergency - picto - PNG.zip
        ERROR: docling.datamodel.document:Input
        document
        Fire - picto - PNG.zip
        with format None does not match any allowed format: (dict_keys([ < InputFormat.DOCX
                                                             : 'docx' >, < InputFormat.PPTX: 'pptx' >, < InputFormat.HTML: 'html' >, < InputFormat.IMAGE: 'image' >, < InputFormat.PDF: 'pdf' >, < InputFormat.ASCIIDOC: 'asciidoc' >, < InputFormat.MD: 'md' >, < InputFormat.CSV: 'csv' >, < InputFormat.XLSX: 'xlsx' >, < InputFormat.XML_USPTO: 'xml_uspto' >, < InputFormat.XML_JATS: 'xml_jats' >, < InputFormat.METS_GBS: 'mets_gbs' >, < InputFormat.JSON_DOCLING: 'json_docling' >, < InputFormat.AUDIO: 'audio' >, < InputFormat.VTT: 'vtt' >]))
        ERROR: docling_jobkit.orchestrators.local.worker:Worker
        0
        failed
        to
        process
        job
        5
        c8a4145 - b329 - 46
        a9 - 88
        f7 - ba9e3d48ed36: File
        format
        not allowed: Fire - picto - PNG.zip
        ERROR: docling.datamodel.document:Input
        document
        GHS - picto - PNG.zip
        with format None does not match any allowed format: (dict_keys([ < InputFormat.DOCX
                                                             : 'docx' >, < InputFormat.PPTX: 'pptx' >, < InputFormat.HTML: 'html' >, < InputFormat.IMAGE: 'image' >, < InputFormat.PDF: 'pdf' >, < InputFormat.ASCIIDOC: 'asciidoc' >, < InputFormat.MD: 'md' >, < InputFormat.CSV: 'csv' >, < InputFormat.XLSX: 'xlsx' >, < InputFormat.XML_USPTO: 'xml_uspto' >, < InputFormat.XML_JATS: 'xml_jats' >, < InputFormat.METS_GBS: 'mets_gbs' >, < InputFormat.JSON_DOCLING: 'json_docling' >, < InputFormat.AUDIO: 'audio' >, < InputFormat.VTT: 'vtt' >]))
        ERROR: docling_jobkit.orchestrators.local.worker:Worker
        1
        failed
        to
        process
        job
        e27b1ba2 - 51
        a3 - 4
        a06 - b90f - 0
        b324f191e5f: File
        format
        not allowed: GHS - picto - PNG.zip
        ERROR: docling.datamodel.document:Input
        document
        Mandatory - picto - PNG.zip
        with format None does not match any allowed format: (dict_keys([ < InputFormat.DOCX
                                                             : 'docx' >, < InputFormat.PPTX: 'pptx' >, < InputFormat.HTML: 'html' >, < InputFormat.IMAGE: 'image' >, < InputFormat.PDF: 'pdf' >, < InputFormat.ASCIIDOC: 'asciidoc' >, < InputFormat.MD: 'md' >, < InputFormat.CSV: 'csv' >, < InputFormat.XLSX: 'xlsx' >, < InputFormat.XML_USPTO: 'xml_uspto' >, < InputFormat.XML_JATS: 'xml_jats' >, < InputFormat.METS_GBS: 'mets_gbs' >, < InputFormat.JSON_DOCLING: 'json_docling' >, < InputFormat.AUDIO: 'audio' >, < InputFormat.VTT: 'vtt' >]))
        ERROR: docling_jobkit.orchestrators.local.worker:Worker
        0
        failed
        to
        process
        job
        9e679615 - 1723 - 4586 - bcb2 - 4
        a0c379db0ca: File
        format
        not allowed: Mandatory - picto - PNG.zip
        ERROR: docling.datamodel.document:Input
        document
        Prohibition - picto - PNG.zip
        with format None does not match any allowed format: (dict_keys([ < InputFormat.DOCX
                                                             : 'docx' >, < InputFormat.PPTX: 'pptx' >, < InputFormat.HTML: 'html' >, < InputFormat.IMAGE: 'image' >, < InputFormat.PDF: 'pdf' >, < InputFormat.ASCIIDOC: 'asciidoc' >, < InputFormat.MD: 'md' >, < InputFormat.CSV: 'csv' >, < InputFormat.XLSX: 'xlsx' >, < InputFormat.XML_USPTO: 'xml_uspto' >, < InputFormat.XML_JATS: 'xml_jats' >, < InputFormat.METS_GBS: 'mets_gbs' >, < InputFormat.JSON_DOCLING: 'json_docling' >, < InputFormat.AUDIO: 'audio' >, < InputFormat.VTT: 'vtt' >]))
        ERROR: docling_jobkit.orchestrators.local.worker:Worker
        0
        failed
        to
        process
        job
        b428d295 - 8843 - 44
        bc - 89
        ff - 2
        a54fe6b5bf6: File
        format
        not allowed: Prohibition - picto - PNG.zip
        ERROR: docling.datamodel.document:Input
        document
        Warning - picto - PNG.zip
        with format None does not match any allowed format: (dict_keys([ < InputFormat.DOCX
                                                             : 'docx' >, < InputFormat.PPTX: 'pptx' >, < InputFormat.HTML: 'html' >, < InputFormat.IMAGE: 'image' >, < InputFormat.PDF: 'pdf' >, < InputFormat.ASCIIDOC: 'asciidoc' >, < InputFormat.MD: 'md' >, < InputFormat.CSV: 'csv' >, < InputFormat.XLSX: 'xlsx' >, < InputFormat.XML_USPTO: 'xml_uspto' >, < InputFormat.XML_JATS: 'xml_jats' >, < InputFormat.METS_GBS: 'mets_gbs' >, < InputFormat.JSON_DOCLING: 'json_docling' >, < InputFormat.AUDIO: 'audio' >, < InputFormat.VTT: 'vtt' >]))
        ERROR: docling_jobkit.orchestrators.local.worker:Worker
        1
        failed
        to
        process
        job
        c6bf7f8e - a1f2 - 4303 - bf97 - feb97342cb8b: File
        format
        not allowed: Warning - picto - PNG.zip

        On
        20
        Oct
        2025, at
        0
        9: 48, Yannick
        Sidney
        Pezeu < yannick.pezeu @ epfl.ch > wrote:

        Bizarre.

        Je
        vais
        essayer
        de
        voir
        ça.

        En
        attendant, il
        semble
        que
        le
        timeout
        de
        traitement
        des
        fichiers
        est
        redescendu
        à
        1
        min
        environ.
        Pourrais
        tu
        le
        remettre
        à
        10
        min ?

        J’ai
        ce
        type d’erreur
        qui
        arrivent
        après
        une
        minute.
        2025 - 10 - 20
        0
        9: 46:00, 568 - ERROR - Docling
        error
        for 'CGHS_Indikatorenbericht_22-06-17.pdf': 504
        Server
        Error: Gateway
        Time - out
        for url: https: // docling.rcp.epfl.ch / v1 / convert / file

        De: Matéo
        Evan
        Muller < mateo.muller @ epfl.ch >
        Envoyé: Sunday, 19
        October
        2025
        18: 0
        9
        À: Yannick
        Sidney
        Pezeu < yannick.pezeu @ epfl.ch >
        Objet: Re: Docling
        Error

        Non, ce
        n’est
        pas
        Docling
        qui
        plante, mais
        il
        ne
        répond
        simplement
        plus
        sur
        son
        endpoint / health, donc
        le
        pod
        est
        redémarré
        après
        30
        secondes
        que
        le
        service
        ne
        répond
        pas.Mais
        aucun
        log
        d’erreur...

        On
        19
        Oct
        2025, at
        18: 07, Yannick
        Sidney
        Pezeu < yannick.pezeu @ epfl.ch > wrote:

        Mince, tu
        penses
        que
        c’est
        vraiment
        Docling
        lui - même
        qui
        plante ?

        Tu as des
        logs
        du
        crash ?

        De: Matéo
        Evan
        Muller < mateo.muller @ epfl.ch >
        Envoyé: Sunday, 19
        October
        2025
        18: 06
        À: Yannick
        Sidney
        Pezeu < yannick.pezeu @ epfl.ch >
        Objet: Re: Docling
        Error

        Hello
        Yannick,

        Je
        vois
        que
        le
        pod
        de
        docling
        a
        déjà
        redémarré
        une
        fois
        pour
        les
        mêmes
        raisons
        avec
        un
        timeout
        de
        10
        secondes.Je
        ne
        vois
        malheureusement
        pas
        ce
        que
        je
        peux
        mettre
        en
        place
        de
        mon
        côté
        pour
        corriger
        le
        problème.Il
        faudrait
        avoir
        un
        moyen
        de
        reproduire
        le
        problème
        et
        ouvrir
        une
        issue
        sur
        GitHub.

        A +
        Matéo

        On
        19
        Oct
        2025, at
        17: 0
        9, Matéo
        Evan
        Muller < mateo.muller @ epfl.ch > wrote:

        Hello
        Yannick,

        Le
        serveur
        Docling
        a
        un
        endpoint / health
        qui
        est
        monitoré
        et
        si
        l’endpoint
        ne
        répond
        pas, le
        pod
        est
        automatiquement
        redémarré.Je
        pense
        que
        le
        serveur
        Docling
        ne
        supporte
        simplement
        pas
        bien
        la
        charge… car
        niveau
        ressources, j’ai
        donné
        largement
        assez
        et
        il
        n’a
        pas
        atteint
        la
        moitié
        avant
        d’arrêter
        de
        répondre.

        J’ai
        passé
        le
        timeout
        du
        health
        check
        à
        10
        secondes, mais
        je
        pense
        simplement
        que
        Docling
        n’est
        pas
        très
        stable.

        Je
        te
        laisse
        réessayer
        et
        me
        confirmer
        que
        tout
        fonctionne
        bien
        ou
        mieux.

        A +

        Matéo

        On
        19
        Oct
        2025, at
        16: 32, Yannick
        Sidney
        Pezeu < yannick.pezeu @ epfl.ch > wrote:

        Hello !

        J’ai
        un
        script
        qui
        devait
        tourner
        ce
        week - end
        et
        il
        a
        eu
        un
        problème
        avec
        des
        erreurs
        docling.Tu as des
        logs
        pour
        qu’on
        sache
        ce
        qui
        s’est
        passé
        avec
        le
        pod
        docling ?


        2025 - 10 - 19
        16: 29:00, 229 - ERROR - Docling
        error
        for 'EPFL_Lagebericht_2016.pdf': 503
        Server
        Error: Service
        Temporarily
        Unavailable
        for url: https: // docling.rcp.epfl.ch / v1 / convert / file

        Je
        suis
        bien
        sur
        le
        VPN
        au
        moment
        de
        l’erreur.
        Le
        script
        a
        marché
        pour
        quelques
        centaines
        de
        document
        et
        soudain
        le
        serveur
        semble
        avoir
        lâché.
        Il
        est
        resté
        down
        quelques
        minutes
        après
        quoi
        il
        semble
        avoir
        redémarré.

        Yannick

