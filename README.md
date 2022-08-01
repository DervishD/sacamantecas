# sacamantecas

`sacamantecas` processes "Mantecas", which are URIs pointing to an entry within
some bibliographic catalogue where book metadata can be obtained, by accessing
the URI, getting that metadata and producing the proper output.

In short, it *"saca las mantecas"*…

The input can be:

- an Excel file (xls/xlsx), containing a list of book titles, each one with its
signature and Manteca. In this case the output will be another Excel file
containing the original data and extra columns with the retrieved metadata.

- a text file containing a list of Mantecas. In this mode of operation the
output file will be another text file containing the retrieved metadata for each
entry.

- a list of Manteca URIs provided as command line arguments. In this case the
metadata is directly written to the console and dumped to an output file.

In addition to this, if any of the sources is prepended with the fake URI scheme
`dump://`, then the contents are not processed, but dumped to files so they can
be used as testing sources in the future.

A Manteca can be ANY kind of URI scheme supported by `urllib`.

The Mantecas are processed according to profiles, which indicate how to properly
process the retrieved contents from the URIs, depending on the bibliographic
catalogue which is being processed. The proper profile is inferred from the URI
itself and resides in the configuration file (`sacamantecas.ini`).

And yes, while the code is commented in English, `sacamantecas` speaks only
Spanish, sorry. Feel free to clone the repo and translate the code, because
short term I don't plan to add `i18n` support.

The program generates two log files, one named `sacamantecas_debug_<timestamp>`
and another named `sacamantecas_log_<timestamp>`. The first one is a debug log,
quite verbose by the way. The second one is the same as the console output of
the program.