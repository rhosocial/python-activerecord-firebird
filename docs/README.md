# rhosocial-activerecord-firebird

Firebird backend implementation for [rhosocial-activerecord](https://github.com/rhosocial/python-activerecord).

## Documentation / 文档

Please select your language / 请选择语言：

- [English Documentation](en_US/README.md)
- [中文文档 (Chinese)](zh_CN/README.md)

## Overview

The Firebird backend brings the ActiveRecord pattern to Firebird through the
`firebird-driver` package. It follows Firebird's version boundaries closely:
several capabilities arrive only in Firebird 4 or 5, and the dialect reports
them per version rather than pretending they always exist.

For the main ActiveRecord framework documentation, please visit the
[python-activerecord docs](https://github.com/rhosocial/python-activerecord/tree/docs/docs).
