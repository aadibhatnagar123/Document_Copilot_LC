def load_corpus(path):
    """Read a text file and return its contents as a string.
    Returns an empty string if the file doesn't exist or can't be read.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"WARNING: corpus file not found: {path}")
        return ""
    except Exception as e:
        print(f"WARNING: could not read {path}: {e}")
        return ""
