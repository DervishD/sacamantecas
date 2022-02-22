# sacamantecas

**This is the HISTORICAL version of `sacamantecas`.**

`sacamantecas` reads an Excel file (xls/xlsx), containing a list of book titles,
each one with its signature and Manteca, which is an URI pointing to an entry
within some bibliographic catalogue where the book metadata can be obtained,
gets that metadata and adds it to each book, producing an output Excel file.

In short, it *"saca las mantecas"*…

If the input file is not an Excel file, it is assumed it contains a list of
Mantecas, that is, a list of URIs pointing to bibliographic entries. In this
mode of operation the output file will not be an Excel file but another text
file containing the retrieved metadata for each entry. This is to make easier,
and faster, the URI retrieval part testing, without the very cumbersome need of
creating Excel files for that purpose only.

And yes, while the code is commented in English, `sacamantecas` speaks only
Spanish, sorry. Feel free to clone the repo and translate the code, because
short term I don't plan to add `i18n` support.
