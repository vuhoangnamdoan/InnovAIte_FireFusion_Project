"""
AWS S3 storage client for shared project data access.

This module centralizes S3 authentication and common bucket operations
(e.g., list, read, write, upload, download) so bushfire and NLP pipelines
can load inputs and persist outputs/artifacts consistently.
"""