from app.symbols import SPOT_SYMBOL_MAP, logical_symbol, spot_symbol


def test_spot_symbol_mapping_round_trips_logical_symbols():
    assert SPOT_SYMBOL_MAP == {
        "AAPLUSDT": "RAAPLUSDT",
        "TSLAUSDT": "RTSLAUSDT",
    }
    assert spot_symbol("AAPLUSDT") == "RAAPLUSDT"
    assert spot_symbol("TSLAUSDT") == "RTSLAUSDT"
    assert logical_symbol("RAAPLUSDT") == "AAPLUSDT"
    assert logical_symbol("RTSLAUSDT") == "TSLAUSDT"


def test_unmapped_symbol_stays_unchanged_at_spot_boundary():
    assert spot_symbol("BTCUSDT") == "BTCUSDT"
    assert logical_symbol("BTCUSDT") == "BTCUSDT"
