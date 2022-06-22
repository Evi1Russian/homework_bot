import logging
import os
import sys
import time
from http import HTTPStatus

from dotenv import load_dotenv

import requests

from exceptions import StatusError, APIStatusCodeError

from telegram import Bot


load_dotenv()


PRACTICUM_TOKEN = os.getenv('TOKEN_PRAKTIKUM')
TELEGRAM_TOKEN = os.getenv('TOKEN_TGBOT')
TELEGRAM_CHAT_ID = os.getenv('MY_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат"""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as error:
        logging.error(f'Ошибка отправки сообщения в телеграм: {error}')
    else:
        logging.info('Сообщение в телеграм успешно отправлено')


def get_api_answer(current_timestamp):
    """Делает запрос к API биржы и возвращает ответ."""

    try:

        timestamp = current_timestamp or int(time.time())
        params = {'from_date': timestamp}
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        logging.error(f'Ошибка при запросе к основному API: {error}')
    if response.status_code != HTTPStatus.OK:
        raise APIStatusCodeError('Сервис недоступен')

    response = response.json()
    return response


def check_response(response):
    """Проверяет наличие всех ключей в ответе API."""
    logging.info('Проверка ответа от API начата')

    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ от API не является словарём: response = {response}'
        )
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(
            'В ответе от API homeworks не список, '
            f'response = {response}'
        )
    current_date = response.get('current_date')
    if not isinstance(current_date, int):
        raise TypeError(
            'В ответе от API  пришло не число, '
            f'current_date = {current_date}'
        )

    return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы."""
    if homework.get('homework_name') is None:
        message = 'Словарь ответа API не содержит ключа homework_name'
        raise KeyError(message)
    elif homework.get('status') is None:
        message = 'Словарь ответа API не содержит ключа status'
        raise KeyError(message)
    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status in HOMEWORK_STATUSES:
        verdict = HOMEWORK_STATUSES[homework_status]
    else:
        message = 'Статус ответа не известен'
        raise StatusError(message)

    homework_name = homework['homework_name']
    verdict = HOMEWORK_STATUSES.get(homework_status)

    message = f'Изменился статус проверки работы "{homework_name}". {verdict}'
    logging.debug(message)

    return message


def check_tokens() -> bool:
    """Проверяет наличие всех переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        error_message = (
            'Отсутствуют обязательные переменные окружения: '
            'Программа принудительно остановлена'
        )
        logging.critical(error_message)
        sys.exit(error_message)

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    current_report = None
    prev_report = current_report

    while True:
        try:
            response = get_api_answer(current_timestamp)

            homeworks = check_response(response)
            homework = homeworks[0]
            current_report = send_message(bot, parse_status(homework))

            current_timestamp = int(time.time())
            if current_report == prev_report:
                logging.debug(
                    'Нет обновлений статуса домашней работы'
                )
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.exception(message)
            time.sleep(RETRY_TIME)
        else:
            logging.info('функция main полностью сработала')


if __name__ == '__main__':
    main()
