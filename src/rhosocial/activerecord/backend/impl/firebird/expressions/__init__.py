# src/rhosocial/activerecord/backend/impl/firebird/expressions/__init__.py
"""Firebird-specific expression implementations.

This package is deprecated; use 'expression' instead.
Re-exports for backward compatibility.
"""
from ..expression.generator import GenIdExpression, NextValueForExpression

__all__ = ["GenIdExpression", "NextValueForExpression"]