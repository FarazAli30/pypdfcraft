# Security policy

Please report vulnerabilities **privately** via GitHub's *Security -> Report a vulnerability* on this repository
(or by e-mail to farazjankhushk@gmail.com), not in public issues. Include a minimal PDF if the issue is triggered by a file.

PDFs are untrusted input: the engine is written in Rust but parses complex formats - keep pypdfcraft up to date.
Problems inside the engine itself should also be reported upstream: <https://github.com/artcraft-android/pdfcraft-android>.
Release wheels are built by GitHub Actions from tagged commits; verify downloads with `SHA256SUMS.txt`.
