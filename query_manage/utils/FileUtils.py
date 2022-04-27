


def file_read(file_name, mode='r', chunk_size=512):
    with open(file_name, mode) as f:
        while True:
            c = f.read(chunk_size)
            if c:
                yield c
            else:
                break