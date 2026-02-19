# Changelog
All notable changes to this project will be documented in this file.

This document is based on the [DervishD changelog specification](https://gist.github.com/DervishD/201c7a51c767c4703f732a2e29a7c3ea).

This project versioning scheme complies with the `Python Packaging Authority` [version specifiers](https://packaging.python.org/en/latest/specifications/version-specifiers/) as defined by the `Python Packaging User Guide`.

## [Development]
### Changed
- Update documentation
- Improve building system

### Added
- Include a `CHANGELOG.md` file

### Fixed
- Normalize use of path-related terms in documentation
- Improve handling of project metadata


## [5.3.0] 2025-11-13
### Changed
- Use PyPA instead of Semantic Versioning scheme. Even though both are (mostly)
  compatible for public releases, the former is better for development releases
- Switch to a `pyproject.toml` building system and project configuration
- Switch to a *src-layout* for repository

### Added
- Separate `dump_url.py` utility

### Fixed
- Do not actually access the network in network-related test units


## [5.2.0] 2025-06-30
### Changed
- Improve error handling

### Fixed
- Configuration for municipal libraries catalogue

## [5.1.0] 2024-06-26
### Changed
- Type annotate the code. This is not an user-visible change, but it is quite an
  important change for the program nonetheless.
- Improve logging framework
- Improve error handling

### Fixed
- Program output for errors
- Handle empty metadata correctly


## [5.0.0] 2023-09-14
The most important change is in the test suite. Instead of a homemade solution,
`pytest` is now used for the test suite.

**BUT** the code has been heavily rewritten and refactored, too, even if it is
not user-visible.

### Removed
- Support for dump-mode

### Changed
- Versioning system. Now Semantic Versioning 2.0.0 is used
- New `pytest`-based test suite
- Code has been adapted to the new test system to improve testability
- Improve command line handling
- Improve logging system
- Simplify HTML parser
- Normalize program exit codes
- Simplify building system

### Added
- Basic logging support when the code is imported rather than run
- Handle URL redirections
- Charset detection for retrieved contents
- Validate parsing profiles at runtime

### Fixed
- Improve `README.md`
- Improve program output messages
- Program output for unhandled errors
- Program output for general errors
- Error when waiting for a keypress at program termination
- Do not wait for a keypress at program termination if code is imported


## [4.4] 2023-09-14
### Fixed
- Handle HTTP errors gracefully


## [4.3] 2023-05-19
### Fixed
- Building system output encoding
- Test suite reference files
- Empty logging messages handling


## [4.2] 2022-09-08
### Fixed
- Wait for a keypress at program termination **only** in transient consoles


## [4.1] 2022-08-02
### Fixed
- Building system output
- Improve building system


## [4.0] 2022-08-01
### Changed
- Improve HTML parser, making it more flexible
- Better looking logging output
- INI file syntax
- Improve building system

### Added
- Basic test suite
- Suport for file:// URLs (both absolute and relative)
- Support for Baratz format catalogues
- Dump mode, where retrieved content is dumped into local HTML files, to make
  testing easier

### Fixed
- Output encoding in Windows
- Error handling
- Logging output now goes to the proper places
- Bug in command line handling
- Wait for a keypress at program termination **only** in real consoles


## [3.3] 2022-04-18
### Changed
- Improved HTML parser
- Support nested metadata

### Added
- Use custom User-Agent when retrieving HTML content
- Profile for BNE catalogue
- Profile for Archivo de Villa catalogue

### Fixed
- Improve program output for unexpected errors
- Improve logging formatting


## [3.2] 2022-03-08
### Changed
- New Python-based building system


## [3.1] 2022-03-04
### Added
- Building system, with more automation
- Support for heading-less Excel files


## [3.0] 2022-03-02
### Changed
- General code refactoring
- Improve command line handling

### Added
- Suport handling of single URLs

### Fixed
- Improve debug logging messages
- Improve logging formatting


## [2.0] 2022-02-28
### Changed
- Modify HTML parser

### Added
- Support URL-based parsing profiles
- Configuration file for specifying profiles. Includes some default profiles
- Detailed logging

### Fixed
- Improve program output


## [1.0] 2022-02-22
First public release

[Development]: https://github.com/DervishD/sacamantecas/compare/v...development
[5.2.0]: https://github.com/DervishD/sacamantecas/compare/v5.1.0...v5.2.0
[5.1.0]: https://github.com/DervishD/sacamantecas/compare/v5.0.0...v5.1.0
[5.0.0]: https://github.com/DervishD/sacamantecas/compare/v4.4...v5.0.0
[4.4]: https://github.com/DervishD/sacamantecas/compare/v4.3...v4.4
[4.3]: https://github.com/DervishD/sacamantecas/compare/v4.2...v4.3
[4.2]: https://github.com/DervishD/sacamantecas/compare/v4.1...v4.2
[4.1]: https://github.com/DervishD/sacamantecas/compare/v4.0...v4.1
[4.0]: https://github.com/DervishD/sacamantecas/compare/v3.3...v4.0
[3.3]: https://github.com/DervishD/sacamantecas/compare/v3.2...v3.3
[3.2]: https://github.com/DervishD/sacamantecas/compare/v3.1...v3.2
[3.1]: https://github.com/DervishD/sacamantecas/compare/v3.0...v3.1
[3.0]: https://github.com/DervishD/sacamantecas/compare/v2.0...v3.0
[2.0]: https://github.com/DervishD/sacamantecas/compare/v1.0...v2.0
[1.0]: https://github.com/DervishD/sacamantecas/releases/tag/v1.0