from app.services.ai_service import replace_internal_user_tokens

def test_replacement_with_name():
    text = "Hello User_1234abcd, welcome back!"
    out = replace_internal_user_tokens(text, {"name": "Alice"})
    assert "Alice" in out and "User_1234abcd" not in out

def test_replacement_with_alias_when_no_name():
    text = "Hi User_deadbeef, how are you?"
    out = replace_internal_user_tokens(text, {"user_id": "deadbeefdeadbeef"})
    assert "User_deadbeef" not in out
    assert any(a in out.lower() for a in ["buddy", "friend", "rockstar", "champ", "pal", "legend", "mate", "star", "trailblazer", "ace"])