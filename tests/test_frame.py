"""取得プロセスと本体をつなぐフレームの読み書きを固定する。"""

import io

import pytest

from nvstore import frame


def test_書いたフレームを同じ順で読み戻せる():
    stream = io.BytesIO()
    frame.write_frame(stream, frame.OPEN, frame.encode_json({"code": 0, "read_count": 2}))
    frame.write_frame(stream, frame.RECORD, b"RA7" + b"x" * 10)
    frame.write_frame(stream, frame.FILE, "RANV2026.nvd".encode("utf-8"))
    frame.write_frame(stream, frame.END)
    stream.seek(0)
    frames = list(frame.read_frames(stream))
    assert [kind for kind, _ in frames] == [frame.OPEN, frame.RECORD, frame.FILE, frame.END]
    assert frame.decode_json(frames[0][1]) == {"code": 0, "read_count": 2}
    assert frames[1][1] == b"RA7" + b"x" * 10
    assert frames[2][1].decode("utf-8") == "RANV2026.nvd"
    assert frames[3][1] == b""


def test_レコードの中身はそのままのバイト列で運ぶ():
    stream = io.BytesIO()
    data = bytes(range(256)) + "馬名".encode("cp932") + b"\r\n"
    frame.write_frame(stream, frame.RECORD, data)
    stream.seek(0)
    assert frame.read_frame(stream) == (frame.RECORD, data)


def test_パイプが閉じたら_None():
    assert frame.read_frame(io.BytesIO()) is None


def test_途中で切れていたら_EOFError():
    stream = io.BytesIO()
    frame.write_frame(stream, frame.RECORD, b"abcdef")
    cut = io.BytesIO(stream.getvalue()[:-2])
    with pytest.raises(EOFError):
        frame.read_frame(cut)
    header_only = io.BytesIO(stream.getvalue()[:3])
    with pytest.raises(EOFError):
        frame.read_frame(header_only)
