import pytest

from services.ai_personalization import render_template, AIPersonalizationService


def test_render_template_basic():
    result = render_template(
        "Привет {first_name} из {company}!",
        {"first_name": "Алексей", "company": "ТехноСофт", "last_name": "", "title": "", "email": ""},
    )
    assert result == "Привет Алексей из ТехноСофт!"


def test_render_template_missing_var():
    result = render_template("Hello {unknown_var}", {"first_name": "A"})
    assert "unknown_var" in result


@pytest.mark.asyncio
async def test_personalize_without_openai():
    svc = AIPersonalizationService(client=None)
    subject, body = await svc.personalize(
        "Тема: {first_name}",
        "Текст для {company}",
        {"first_name": "Иван", "company": "DataFlow", "last_name": "", "title": "", "email": ""},
    )
    assert "Иван" in subject
    assert "DataFlow" in body


def test_render_empty_variables():
    result = render_template("Hi {first_name}", {"first_name": "", "last_name": "", "company": "", "title": "", "email": ""})
    assert result == "Hi "
