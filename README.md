# sacamantecas

`sacamantecas` processes URLs pointing to an entry within some bibliographic
catalogue where book metadata can be obtained, by retrieving the URL, parsing it
to get the metadata and storing the metadata.

In short, it *"saca las mantecas"*…

The input can be:

- an Excel file (xls/xlsx), containing a list of book titles, each one with its
signature and URL. In this case the output will be another Excel file containing
the original data and extra columns with the retrieved metadata.

- a text file containing a list of URLs. In this mode of operation the output
file will be another text file containing the retrieved metadata for each entry.

- a list of URLs provided as command line arguments. In this case the metadata
is directly written to the console and dumped to an output file.

The URLs can be any scheme supported by `urllib`.

The URLs are processed according to profiles, which indicate how to properly
process the retrieved contents, depending on the bibliographic catalogue which
is being processed. The proper profile is inferred from the URL itself and
resides in the configuration file (`sacamantecas.ini`).

And yes, while the code is commented in English, `sacamantecas` speaks only
Spanish, sorry. Feel free to clone the repo and translate the code, because
short term I don't plan to add `i18n` support.

The application generates two log files, one named `sacamantecas_debug_<timestamp>`
and another named `sacamantecas_log_<timestamp>`. The first one is a debug log,
quite verbose by the way. The second one is the same as the console output of
the application.