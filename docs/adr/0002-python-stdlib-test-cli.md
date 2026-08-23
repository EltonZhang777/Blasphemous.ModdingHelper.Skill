# Use a Python standard-library CLI for mod testing

Status: accepted

The mod test workflow uses one Python 3 standard-library CLI with `argparse` as its cross-platform implementation boundary. Native Windows PowerShell and native Linux/macOS Bash invoke the same CLI, while compatibility shells such as Git Bash, Cygwin, WSL, and Proton are rejected by the CLI contract.

This is an intentional exception to the repository's general preference for a shared Node implementation with thin shell wrappers. The mod test requirement explicitly selects Python, and the workflow needs a portable filesystem, process, and profile model without adding runtime dependencies to the installed skill. Replacing it with a Node implementation would contradict the accepted spec and create two competing implementation boundaries.

The CLI must remain standard-library-only, keep platform-specific behavior behind the Python public entry point, and preserve the native-shell support and compatibility-shell rejection defined by the mod test context.
