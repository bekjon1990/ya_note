# test_logic.py
from pytest_django.asserts import assertRedirects
# Импортируем функции для проверки редиректа и ошибки формы:
from pytest_django.asserts import assertRedirects, assertFormError
from pytils.translit import slugify
# Импортируем из модуля forms сообщение об ошибке:
from notes.forms import WARNING
from django.urls import reverse
import pytest
from notes.models import Note
from http import HTTPStatus


# Указываем фикстуру form_data в параметрах теста.
def test_user_can_create_note(author_client, author, form_data):
    url = reverse('notes:add')
    # В POST-запросе отправляем данные, полученные из фикстуры form_data:
    response = author_client.post(url, data=form_data)
    # Проверяем, что был выполнен редирект на страницу успешного добавления заметки:
    assertRedirects(response, reverse('notes:success'))
    # Считаем общее количество заметок в БД, ожидаем 1 заметку.
    assert Note.objects.count() == 1
    # Чтобы проверить значения полей заметки -
    # получаем её из базы при помощи метода get():
    new_note = Note.objects.get()
    # Сверяем атрибуты объекта с ожидаемыми.
    assert new_note.title == form_data['title']
    assert new_note.text == form_data['text']
    assert new_note.slug == form_data['slug']
    assert new_note.author == author
    # Вроде бы здесь нарушен принцип "один тест - одна проверка";
    # но если хоть одна из этих проверок провалится -
    # весь тест можно признать провалившимся, а последующие невыполненные проверки
    # не внесли бы в отчёт о тесте ничего принципиально важного.


# Добавляем маркер, который обеспечит доступ к базе данных:
@pytest.mark.django_db
def test_anonymous_user_cant_create_note(client, form_data):
    url = reverse('notes:add')
    # Через анонимный клиент пытаемся создать заметку:
    response = client.post(url, data=form_data)
    login_url = reverse('users:login')
    expected_url = f'{login_url}?next={url}'
    # Проверяем, что произошла переадресация на страницу логина:
    assertRedirects(response, expected_url)
    # Считаем количество заметок в БД, ожидаем 0 заметок.
    assert Note.objects.count() == 0


# Вызываем фикстуру отдельной заметки, чтобы в базе появилась запись.
def test_not_unique_slug(author_client, note, form_data):
    url = reverse('notes:add')
    # Подменяем slug новой заметки на slug уже существующей записи:
    form_data['slug'] = note.slug
    # Пытаемся создать новую заметку:
    response = author_client.post(url, data=form_data)
    # Проверяем, что в ответе содержится ошибка формы для поля slug:
    assertFormError(response, 'form', 'slug', errors=(note.slug + WARNING))
    # Убеждаемся, что количество заметок в базе осталось равным 1:
    assert Note.objects.count() == 1


def test_empty_slug(author_client, form_data):
    url = reverse('notes:add')
    # Убираем поле slug из словаря:
    form_data.pop('slug')
    response = author_client.post(url, data=form_data)
    # Проверяем, что даже без slug заметка была создана:
    assertRedirects(response, reverse('notes:success'))
    assert Note.objects.count() == 1
    # Получаем созданную заметку из базы:
    new_note = Note.objects.get()
    # Формируем ожидаемый slug:
    expected_slug = slugify(form_data['title'])
    # Проверяем, что slug заметки соответствует ожидаемому:
    assert new_note.slug == expected_slug


def test_author_can_edit_note(author_client, form_data, note):
    # Получаем адрес страницы редактирования заметки:
    url = reverse('notes:edit', args=(note.slug,))
    # В POST-запросе на адрес редактирования заметки
    # отправляем form_data - новые значения для полей заметки:
    response = author_client.post(url, form_data)
    # Проверяем редирект:
    assertRedirects(response, reverse('notes:success'))
    # Обновляем объект заметки note: получаем обновлённые данные из БД:
    note.refresh_from_db()
    # Проверяем, что атрибуты заметки соответствуют обновлённым:
    assert note.title == form_data['title']
    assert note.text == form_data['text']
    assert note.slug == form_data['slug']


def test_other_user_cant_edit_note(admin_client, form_data, note):
    url = reverse('notes:edit', args=(note.slug,))
    response = admin_client.post(url, form_data)
    # Проверяем, что страница не найдена:
    assert response.status_code == HTTPStatus.NOT_FOUND
    # Получаем новый объект запросом из БД.
    note_from_db = Note.objects.get(id=note.id)
    # Проверяем, что атрибуты объекта из БД равны атрибутам заметки до запроса.
    assert note.title == note_from_db.title
    assert note.text == note_from_db.text
    assert note.slug == note_from_db.slug


@pytest.mark.parametrize(
    # В качестве параметров передаем name и args для reverse.
    'name, args',
    (
            # Для тестирования страницы создания заметки
            # никакие дополнительные аргументы для reverse() не нужны.
            ('notes:delete', pytest.lazy_fixture('slug_for_args')),
            # Для тестирования страницы редактирования заметки нужен slug заметки.
            ('notes:delete', pytest.lazy_fixture('slug_for_args'))
    )
)
def test_author_can_delete_note(author_client, form_data, name, args):
    # Формируем URL.
    url = reverse(name, args=args)
    # Запрашиваем нужную страницу:
    response = author_client.get(url)
    # Проверяем, есть ли объект формы в словаре контекста:
    assert 'note' in response.context
