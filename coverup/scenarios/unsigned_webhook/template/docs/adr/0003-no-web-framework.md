# ADR 0003: No web framework

- Status: accepted (2025-02-11)

The HTTP surface is a health check and a handful of webhook routes. We use a small request/response layer
(`comms/http.py`, `comms/app.py`) and a WSGI adapter instead of a framework, and keep runtime code on the standard
library. Fewer dependencies to patch, and the webhook path stays small enough to read in one sitting.

Revisit if we grow a public API (there's no plan to).
