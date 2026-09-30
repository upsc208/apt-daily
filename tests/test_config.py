from src.config import Config, get_lawd_codes

def test_config_paths():
    assert Config.DATA_DIR.exists()
    assert Config.DB_PATH.name == "apt_trade.db"

def test_lawd_codes_loading():
    codes = get_lawd_codes()
    assert len(codes) >= 200
    assert any(c["code"] == "11680" and c["sigungu"] == "강남구" for c in codes)
