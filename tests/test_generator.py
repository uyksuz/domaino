from generator import get_slice, total_count

def test_total_count_3():
    assert total_count(3) == 17576

def test_total_count_4():
    assert total_count(4) == 456976

def test_total_count_5():
    assert total_count(5) == 11881376

def test_get_slice_first_three():
    result = get_slice(3, 0, 3)
    assert result == ['aaa.com', 'aab.com', 'aac.com']

def test_get_slice_with_offset():
    result = get_slice(3, 1, 2)
    assert result == ['aab.com', 'aac.com']

def test_get_slice_all_have_dot_com():
    result = get_slice(3, 0, 10)
    assert all(d.endswith('.com') for d in result)

def test_get_slice_correct_length():
    result = get_slice(4, 0, 5)
    assert all(len(d) == 8 for d in result)  # 4 chars + '.com'

def test_get_slice_beyond_total_returns_empty():
    result = get_slice(3, 17576, 10)
    assert result == []

def test_get_slice_partial_at_end():
    result = get_slice(3, 17574, 10)
    assert len(result) == 2
