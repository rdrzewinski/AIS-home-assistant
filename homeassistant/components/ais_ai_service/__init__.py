"""
Support for functionality to have conversations with AI-Speaker.

"""
import asyncio
import logging
import re
import warnings
import json
import voluptuous as vol
import datetime
import requests
import os
from homeassistant import core
from homeassistant.loader import bind_hass
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_OFF,
    SERVICE_TURN_ON, ATTR_UNIT_OF_MEASUREMENT, SERVICE_OPEN_COVER, SERVICE_CLOSE_COVER,
    STATE_ON, STATE_OFF, STATE_HOME, STATE_NOT_HOME, STATE_UNKNOWN, STATE_OPEN, STATE_OPENING, STATE_CLOSED,
    STATE_CLOSING, STATE_PLAYING, STATE_PAUSED, STATE_IDLE, STATE_STANDBY, STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_NIGHT, STATE_ALARM_ARMED_CUSTOM_BYPASS, STATE_ALARM_PENDING,
    STATE_ALARM_ARMING, STATE_ALARM_DISARMING, STATE_ALARM_TRIGGERED, STATE_LOCKED, STATE_UNLOCKED,
    STATE_UNAVAILABLE, STATE_OK, STATE_PROBLEM, ATTR_ASSUMED_STATE)
from homeassistant.helpers import intent, config_validation as cv
from homeassistant.components import ais_cloud
import homeassistant.components.mqtt as mqtt
from homeassistant.components import ais_drives_service
import homeassistant.ais_dom.ais_global as ais_global
aisCloudWS = ais_cloud.AisCloudWS()

REQUIREMENTS = ['fuzzywuzzy==0.15.1', 'babel']
# DEPENDENCIES = ['http']

ATTR_TEXT = 'text'
DOMAIN = 'ais_ai_service'
G_HTTP_REST_SERVICE_BASE_URL = 'http://{}:8122'

REGEX_TURN_COMMAND = re.compile(r'turn (?P<name>(?: |\w)+) (?P<command>\w+)')

SERVICE_PROCESS_SCHEMA = vol.Schema({
    vol.Required(ATTR_TEXT): cv.string,
})

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({
    vol.Optional('intents'): vol.Schema({
        cv.string: vol.All(cv.ensure_list, [cv.string])
    })
})}, extra=vol.ALLOW_EXTRA)

INTENT_GET_TIME = 'AisGetTime'
INTENT_GET_DATE = 'AisGetDate'
INTENT_PLAY_RADIO = 'AisPlayRadio'
INTENT_PLAY_PODCAST = 'AisPlayPodcast'
INTENT_PLAY_YT_MUSIC = 'AisPlayYtMusic'
INTENT_PLAY_SPOTIFY = 'AisPlaySpotify'
INTENT_ASK_QUESTION = 'AisAskQuestion'
INTENT_CHANGE_CONTEXT = 'AisChangeContext'
INTENT_GET_WEATHER = 'AisGetWeather'
INTENT_GET_WEATHER_48 = 'AisGetWeather48'
INTENT_STATUS = 'AisStatusInfo'
INTENT_TURN_ON = 'AisTurnOn'
INTENT_TURN_OFF = 'AisTurnOff'
INTENT_LAMPS_ON = 'AisLampsOn'
INTENT_LAMPS_OFF = 'AisLampsOff'
INTENT_SWITCHES_ON = 'AisSwitchesOn'
INTENT_SWITCHES_OFF = 'AisSwitchesOff'
INTENT_OPEN_COVER = 'AisCoverOpen'
INTENT_CLOSE_COVER = 'AisCoverClose'
INTENT_STOP = 'AisStop'
INTENT_PLAY = 'AisPlay'
INTENT_NEXT = 'AisNext'
INTENT_PREV = 'AisPrev'
INTENT_SCENE = 'AisSceneActive'
INTENT_SAY_IT = 'AisSayIt'
INTENT_CLIMATE_SET_TEMPERATURE = 'AisClimateSetTemperature'
INTENT_CLIMATE_SET_AWAY = 'AisClimateSetAway'
INTENT_CLIMATE_UNSET_AWAY = 'AisClimateUnSetAway'
INTENT_CLIMATE_SET_ALL_ON = 'AisClimateSetAllOn'
INTENT_CLIMATE_SET_ALL_OFF = 'AisClimateSetAllOff'

REGEX_TYPE = type(re.compile(''))

_LOGGER = logging.getLogger(__name__)
GROUP_VIEWS = ['Pomoc', 'Twój Dom', 'Audio', 'Ustawienia']
CURR_GROUP_VIEW = None
# group entities in each group view, see main_ais_groups.yaml
GROUP_ENTITIES = []
ALL_AIS_SENSORS = []
CURR_GROUP = None
CURR_ENTITIE = None
CURR_ENTITIE_ENTERED = False
CURR_BUTTON_CODE = None
CURR_BUTTON_LONG_PRESS = False
CURR_ENTITIE_POSITION = None
ALL_SWITCHES = ["input_boolean", "automation", "switch", "light", "media_player", "script"]

# ais-dom virtual keyboard
# kodowała to Asia Raczkowska w 2019 roku
VIRTUAL_KEYBOARD_MODE = ['Litery', 'Wielkie litery', 'Cyfry', 'Znaki specjalne', 'Usuwanie']
CURR_VIRTUAL_KEYBOARD_MODE = None
VIRTUAL_KEYBOARD_LETTERS = ['-', 'A', 'Ą', 'B', 'C', 'Ć', 'D', 'E', 'Ę', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'Ł', 'M',
                            'N', 'Ń', 'O', 'Ó', 'P', 'Q', 'R', 'S', 'Ś', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', 'Ź', 'Ż']
VIRTUAL_KEYBOARD_NUMBERS = ['-', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
VIRTUAL_KEYBOARD_SYMBOLS = ['-', ' ', '!', '"', '#', '$', '%', '&', "'", '(', ')', '*', '+', ',', '-', '_', '.', '/',
                            ':', ';', '<', '=', '>', '?', '@', '[', '\\', ']', '^', '{', '|', '}']
VIRTUAL_KEYBOARD_SYMBOLS_NAMES = ['-', 'spacja', 'wykrzyknik', 'cudzysłów', 'hash', 'dolar', 'procent', 'symbol and',
                                  'pojedynczy cudzysłów', 'nawias otwierający', 'nawias zamykający', 'gwiazdka',
                                  'plus', 'przecinek', 'myślnik', 'podkreślenie dolne', 'kropka', 'ukośnik prawy',
                                  'dwukropek', 'średnik', 'znak mniejszości', 'znak równości', 'znak większości',
                                  'znak zapytania', 'małpa', 'kwadratowy nawias otwierający', 'ukośnik lewy',
                                  'kwadratowy nawias zamykający', 'daszek', 'nawias klamrowy otwierający',
                                  'kreska pionowa', 'nawias klamrowy zamykający']
VIRTUAL_KEYBOARD_DELETE = ['-', 'ostatni znak', 'ostatni wyraz', 'całe pole']
CURR_VIRTUAL_KEYBOARD_VALUE = None
CURR_VIRTUAL_KEY = None
# ais-dom virtual keyboard

GLOBAL_TTS_TEXT = None

def get_tts_text():
    return GLOBAL_TTS_TEXT


def isSwitch(entity_id):
    global ALL_SWITCHES
    # problem with startswith and tuple of strings
    for s in ALL_SWITCHES:
        if entity_id.startswith(s):
            return True
    return False


@core.callback
@bind_hass
def async_register(hass, intent_type, utterances):
    """Register an intent.
    Registrations don't require conversations to be loaded. They will become
    active once the conversation component is loaded.
    """
    intents = hass.data.get(DOMAIN)

    if intents is None:
        intents = hass.data[DOMAIN] = {}

    conf = intents.get(intent_type)

    if conf is None:
        conf = intents[intent_type] = []

    for utterance in utterances:
        if isinstance(utterance, REGEX_TYPE):
            conf.append(utterance)
        else:
            conf.append(_create_matcher(utterance))


def translate_state(info_data):
    if not info_data:
        info_data = ""
    elif info_data == STATE_ON:
        info_data = "włączone"
    elif info_data == STATE_OFF:
        info_data = "wyłączone"
    elif info_data == STATE_HOME:
        info_data = "w domu"
    elif info_data == STATE_NOT_HOME:
        info_data = "poza domem"
    elif info_data == STATE_UNKNOWN:
        info_data = "status nieznany"
    elif info_data == STATE_OPEN:
        info_data = "otwarty"
    elif info_data == STATE_OPENING:
        info_data = "otwieranie"
    elif info_data == STATE_CLOSED:
        info_data = "zamknięty"
    elif info_data == STATE_CLOSING:
        info_data = "zamykanie"
    elif info_data == STATE_PAUSED:
        info_data = "pauza"
    elif info_data == STATE_PLAYING:
        info_data = "odtwarzanie"
    elif info_data == STATE_IDLE:
        info_data = "status bezczynny"
    elif info_data == STATE_STANDBY:
        info_data = "status bezczynny"
    elif info_data == STATE_ALARM_DISARMED:
        info_data = "status rozbrojony"
    elif info_data == STATE_ALARM_ARMED_HOME:
        info_data = "status uzbrojony w domu"
    elif info_data == STATE_ALARM_ARMED_AWAY:
        info_data = "status uzbrojony poza domem"
    elif info_data == STATE_ALARM_ARMED_NIGHT:
        info_data = "status uzbrojony noc"
    elif info_data == STATE_ALARM_ARMED_CUSTOM_BYPASS:
        info_data = "status uzbrojony własny"
    elif info_data == STATE_ALARM_ARMING:
        info_data = "alarm uzbrajanie"
    elif info_data == STATE_ALARM_DISARMING:
        info_data = "alarm rozbrajanie"
    elif info_data == STATE_ALARM_TRIGGERED:
        info_data = "alarm powiadomiony"
    elif info_data == STATE_LOCKED:
        info_data = "zamknięty"
    elif info_data == STATE_UNLOCKED:
        info_data = "otwarty"
    elif info_data == STATE_UNAVAILABLE:
        info_data = "niedostępny"
    elif info_data == STATE_OK:
        info_data = "ok"
    elif info_data == STATE_PROBLEM:
        info_data = "problem"
    elif info_data == "above_horizon":
        info_data = "powyżej horyzontu"
    elif info_data == "below_horizon":
        info_data = "poniżej horyzontu"

    return info_data


def get_next(arra, curr):
    _first = None
    _curr = None
    _next = None
    for a in arra:
        # ignore empy option
        if a != ais_global.G_EMPTY_OPTION:
            if _curr is not None and _next is None:
                _next = a
            if _first is None:
                _first = a
            if curr == a:
                _curr = a
    if _next is not None:
        return _next
    else:
        return _first


def get_prev(arra, curr):
    _last = None
    _curr = None
    _prev = None
    for a in arra:
        # ignore empy option
        if a != ais_global.G_EMPTY_OPTION:
            _last = a
            if curr == a:
                _curr = a
            if _curr is None:
                _prev = a
    if _prev is not None:
        return _prev
    else:
        return _last


# Group views: Dom -> Audio -> Ustawienia -> Pomoc
def get_curr_group_view():
    if CURR_GROUP_VIEW is None:
        return GROUP_VIEWS[0]
    return CURR_GROUP_VIEW


def say_curr_group_view(hass):
    _say_it(hass, get_curr_group_view(), None)


def set_curr_group_view():
    # set focus on current menu group view
    global CURR_GROUP_VIEW
    global CURR_GROUP
    global CURR_ENTITIE
    global CURR_ENTITIE_ENTERED
    global CURR_ENTITIE_POSITION
    CURR_GROUP = None
    CURR_ENTITIE = None
    CURR_ENTITIE_ENTERED = False
    CURR_ENTITIE_POSITION = None
    CURR_GROUP_VIEW = get_curr_group_view()


def set_next_group_view():
    # set focus on next menu group view
    global CURR_GROUP_VIEW
    CURR_GROUP_VIEW = get_next(GROUP_VIEWS, get_curr_group_view())
    # to reset
    set_curr_group_view()


def set_prev_group_view():
    # set focus on prev menu group view
    global CURR_GROUP_VIEW
    CURR_GROUP_VIEW = get_prev(GROUP_VIEWS, get_curr_group_view())
    # to reset
    set_curr_group_view()


# virtual keybord
# Group views: Litery -> Wielkie litery -> Cyfry -> Znaki specjalne -> Usuwanie
def get_curr_virtual_keyboard_mode():
    if CURR_VIRTUAL_KEYBOARD_MODE is None:
        return VIRTUAL_KEYBOARD_MODE[0]
    return CURR_VIRTUAL_KEYBOARD_MODE


def set_next_virtual_keyboard_mode():
    global CURR_VIRTUAL_KEYBOARD_MODE
    global CURR_VIRTUAL_KEY
    CURR_VIRTUAL_KEY = None
    CURR_VIRTUAL_KEYBOARD_MODE = get_next(VIRTUAL_KEYBOARD_MODE, get_curr_virtual_keyboard_mode())


def set_prev_virtual_keyboard_mode():
    global CURR_VIRTUAL_KEYBOARD_MODE
    global CURR_VIRTUAL_KEY
    CURR_VIRTUAL_KEY = None
    CURR_VIRTUAL_KEYBOARD_MODE = get_prev(VIRTUAL_KEYBOARD_MODE, get_curr_virtual_keyboard_mode())


def say_curr_virtual_keyboard_mode(hass):
    _say_it(hass, get_curr_virtual_keyboard_mode(), None)


def get_curr_virtual_key():
    if CURR_VIRTUAL_KEY is not None:
        return str(CURR_VIRTUAL_KEY)
    km = get_curr_virtual_keyboard_mode()
    if km == "Litery":
        return VIRTUAL_KEYBOARD_LETTERS[0]
    elif km == "Wielkie litery":
        return VIRTUAL_KEYBOARD_LETTERS[0]
    elif km == "Cyfry":
        return VIRTUAL_KEYBOARD_NUMBERS[0]
    elif km == "Znaki specjalne":
        return VIRTUAL_KEYBOARD_SYMBOLS[0]
    elif km == "Usuwanie":
        return VIRTUAL_KEYBOARD_DELETE[0]


def set_next_virtual_key():
    global CURR_VIRTUAL_KEY
    km = get_curr_virtual_keyboard_mode()
    if km == "Litery":
        CURR_VIRTUAL_KEY = get_next(VIRTUAL_KEYBOARD_LETTERS, get_curr_virtual_key())
    elif km == "Wielkie litery":
        CURR_VIRTUAL_KEY = get_next(VIRTUAL_KEYBOARD_LETTERS, get_curr_virtual_key())
    elif km == "Cyfry":
        CURR_VIRTUAL_KEY = get_next(VIRTUAL_KEYBOARD_NUMBERS, get_curr_virtual_key())
    elif km == "Znaki specjalne":
        CURR_VIRTUAL_KEY = get_next(VIRTUAL_KEYBOARD_SYMBOLS, get_curr_virtual_key())
    elif km == "Usuwanie":
        CURR_VIRTUAL_KEY = get_next(VIRTUAL_KEYBOARD_DELETE, get_curr_virtual_key())


def set_prev_virtual_key():
    global CURR_VIRTUAL_KEY
    km = get_curr_virtual_keyboard_mode()
    if km == "Litery":
        CURR_VIRTUAL_KEY = get_prev(VIRTUAL_KEYBOARD_LETTERS, get_curr_virtual_key())
    elif km == "Wielkie litery":
        CURR_VIRTUAL_KEY = get_prev(VIRTUAL_KEYBOARD_LETTERS, get_curr_virtual_key())
    elif km == "Cyfry":
        CURR_VIRTUAL_KEY = get_prev(VIRTUAL_KEYBOARD_NUMBERS, get_curr_virtual_key())
    elif km == "Znaki specjalne":
        CURR_VIRTUAL_KEY = get_prev(VIRTUAL_KEYBOARD_SYMBOLS, get_curr_virtual_key())
    elif km == "Usuwanie":
        CURR_VIRTUAL_KEY = get_prev(VIRTUAL_KEYBOARD_DELETE, get_curr_virtual_key())


def say_curr_virtual_key(hass):
    key = get_curr_virtual_key()
    km = get_curr_virtual_keyboard_mode()
    text = ""
    if km == "Litery":
        text = "" + key.lower()
    elif km == "Wielkie litery":
        text = "" + key
    elif km == "Cyfry":
        text = "" + key
    elif km == "Znaki specjalne":
        idx = VIRTUAL_KEYBOARD_SYMBOLS.index(key)
        text = "" + VIRTUAL_KEYBOARD_SYMBOLS_NAMES[idx]
    elif km == "Usuwanie":
        text = "" + key

    _say_it(hass, text, None)


def reset_virtual_keyboard(hass):
    global CURR_VIRTUAL_KEYBOARD_MODE
    global CURR_VIRTUAL_KEY
    global CURR_VIRTUAL_KEYBOARD_VALUE
    CURR_VIRTUAL_KEYBOARD_MODE = None
    CURR_VIRTUAL_KEY = None
    CURR_VIRTUAL_KEYBOARD_VALUE = None
    # reset field value
    hass.services.call('input_text', 'set_value', {
        "entity_id": CURR_ENTITIE, "value": ""})


# Groups in Groups views
def get_curr_group():
    global CURR_GROUP
    if CURR_GROUP is None:
        # take the first one from Group view
        for group in GROUP_ENTITIES:
            if group['remote_group_view'] == get_curr_group_view():
                CURR_GROUP = group
    return CURR_GROUP


def get_curr_group_idx():
    idx = 0
    for group in GROUP_ENTITIES:
        if group['entity_id'] == get_curr_group()['entity_id']:
            return idx
        idx += 1
    return idx


def say_curr_group(hass):
    _say_it(hass, get_curr_group()['friendly_name'], None)


def set_bookmarks_curr_group(hass):
    for idx, g in enumerate(GROUP_ENTITIES, start=0):
        if g['entity_id'] == 'group.bookmarks':
            set_curr_group(hass, g)


def set_curr_group(hass, group):
    # set focus on current menu group view
    global CURR_GROUP_VIEW
    global CURR_GROUP
    global CURR_ENTITIE
    global CURR_ENTITIE_ENTERED
    global CURR_ENTITIE_POSITION
    # the entitie can be selected or focused
    CURR_ENTITIE = None
    CURR_ENTITIE_ENTERED = False
    CURR_ENTITIE_POSITION = None
    if group is None:
        CURR_GROUP = get_curr_group()

        hass.states.async_set(
            'binary_sensor.selected_entity',
            CURR_GROUP['entity_id'])
    else:
        CURR_GROUP_VIEW = group['remote_group_view']
        CURR_GROUP = group


def set_next_group(hass):
    # set focus on next group in focused view
    global CURR_GROUP
    first_group_in_view = None
    curr_group_in_view = None
    next_group_in_view = None
    for group in GROUP_ENTITIES:
        if group['remote_group_view'] == get_curr_group_view():
            # select the first group
            if curr_group_in_view is not None and next_group_in_view is None:
                next_group_in_view = group
            if first_group_in_view is None:
                first_group_in_view = group
            if CURR_GROUP['entity_id'] == group['entity_id']:
                curr_group_in_view = group

    if next_group_in_view is not None:
        CURR_GROUP = next_group_in_view
    else:
        CURR_GROUP = first_group_in_view
    # to reset
    set_curr_group(hass, CURR_GROUP)


def set_prev_group(hass):
    # set focus on prev group in focused view
    global CURR_GROUP
    last_group_in_view = None
    curr_group_in_view = None
    prev_group_in_view = None
    for group in GROUP_ENTITIES:
        if group['remote_group_view'] == get_curr_group_view():
            # select the last group
            last_group_in_view = group
            if CURR_GROUP['entity_id'] == group['entity_id']:
                curr_group_in_view = group
            if curr_group_in_view is None:
                prev_group_in_view = group
    if prev_group_in_view is not None:
        CURR_GROUP = prev_group_in_view
    else:
        CURR_GROUP = last_group_in_view
    # to reset
    set_curr_group(hass, CURR_GROUP)


# entity in group
def get_curr_entity():
    global CURR_ENTITIE
    if CURR_ENTITIE is None:
        CURR_ENTITIE = GROUP_ENTITIES[get_curr_group_idx()]['entities'][0]
    return CURR_ENTITIE


def get_curr_entity_idx():
    idx = 0
    for item in GROUP_ENTITIES[get_curr_group_idx()]['entities']:
        if item == get_curr_entity():
            return idx
        idx += 1


def set_curr_entity(hass, entity):
    # set focus on current entity
    global CURR_ENTITIE
    global CURR_ENTITIE_POSITION
    if entity is None:
        CURR_ENTITIE = get_curr_entity()
    else:
        CURR_ENTITIE = entity
    CURR_ENTITIE_POSITION = None
    hass.states.async_set(
        'binary_sensor.selected_entity',
        CURR_ENTITIE)


def set_next_entity(hass):
    # set next entity
    global CURR_ENTITIE
    entity_idx = get_curr_entity_idx()
    group_idx = get_curr_group_idx()
    l_group_len = len(GROUP_ENTITIES[group_idx]['entities'])
    if entity_idx + 1 == l_group_len:
        entity_idx = 0
    else:
        entity_idx = entity_idx + 1
    CURR_ENTITIE = GROUP_ENTITIES[group_idx]['entities'][entity_idx]
    # to reset variables
    set_curr_entity(hass, None)
    say_curr_entity(hass)


def set_prev_entity(hass):
    # set prev entity
    global CURR_ENTITIE
    idx = get_curr_entity_idx()
    l_group_len = len(GROUP_ENTITIES[get_curr_group_idx()]['entities'])
    if idx == 0:
        idx = l_group_len - 1
    else:
        idx = idx - 1
    CURR_ENTITIE = GROUP_ENTITIES[get_curr_group_idx()]['entities'][idx]
    # to reset variables
    set_curr_entity(hass, None)
    say_curr_entity(hass)


def say_curr_entity(hass):
    # check if we have selected item
    entity_id = get_curr_entity()
    state = hass.states.get(entity_id)
    if state is None:
        _say_it(hass, "Brak pozycji", None)
        return
    text = state.attributes.get('text')
    info_name = state.attributes.get('friendly_name')
    info_data = state.state
    info_unit = state.attributes.get('unit_of_measurement')
    if not text:
        text = ""
    # handle special cases...
    if entity_id == "sensor.ais_knowledge_answer":
        _say_it(hass, "Odpowiedź: " + text, None)
        return
    elif entity_id == 'sensor.dyski':
        _say_it(hass, "Dysk wewnętrzny", None)
        hass.services.call(
            'ais_drives_service',
            'browse_path', {"path": '/data/data/pl.sviete.dom/files/home/dom'})
        return
    elif entity_id == 'input_select.ais_bookmark_last_played':
        _say_it(hass, info_name + " " + info_data.replace("Local;", ""), None)
        return
    elif entity_id.startswith('script.'):
        _say_it(hass, info_name + " Naciśnij OK/WYKONAJ by uruchomić.", None)
        return
    elif entity_id.startswith('input_text.'):
        if CURR_BUTTON_CODE == 4:
            if CURR_VIRTUAL_KEYBOARD_VALUE is None:
                _say_it(hass, "Nic nie wpisałeś", None)
            else:
                _say_it(hass, "Wpisałeś " + CURR_VIRTUAL_KEYBOARD_VALUE, None)
        else:
            _say_it(hass, info_name + " " + info_data + ". Naciśnij OK by wpisać.", None)
        return
    elif entity_id.startswith('input_select.'):
        if CURR_BUTTON_CODE == 4:
            if info_data == ais_global.G_EMPTY_OPTION:
                _say_it(hass, "Brak wyboru", None)
            else:
                _say_it(hass, "Wybrałeś " + info_data, None)
        else:
            if info_data != ais_global.G_EMPTY_OPTION:
                _say_it(hass, info_name + " " + info_data + ". Naciśnij OK by zmienić.", None)
            else:
                _say_it(hass, info_name + " " + info_data + ". Naciśnij OK by wybrać.", None)
        return
    # normal case
    # decode None
    if not info_name:
        info_name = ""
    info_data = translate_state(info_data)
    if not info_unit:
        info_unit = ""
    info = "%s %s %s" % (info_name, info_data, info_unit)
    _say_it(hass, info, None)


def get_curent_position(hass):
    # return the entity focused position
    global CURR_ENTITIE_POSITION
    if CURR_ENTITIE_POSITION is None:
        CURR_ENTITIE_POSITION = hass.states.get(CURR_ENTITIE).state
    return CURR_ENTITIE_POSITION


def commit_current_position(hass):
    if CURR_ENTITIE.startswith('input_select.'):
        # force the change - to trigger the state change for automation
        position = get_curent_position(hass)
        hass.services.call(
            'input_select',
            'select_option', {
                "entity_id": CURR_ENTITIE,
                "option": ais_global.G_EMPTY_OPTION})
        hass.block_till_done()
        hass.services.call(
            'input_select',
            'select_option', {
                "entity_id": CURR_ENTITIE,
                "option": position})
    elif CURR_ENTITIE.startswith('input_number.'):
        hass.services.call(
            'input_number',
            'set_value', {
                "entity_id": CURR_ENTITIE,
                "value": get_curent_position(hass)})

    if CURR_ENTITIE == "input_select.ais_android_wifi_network":
        _say_it(hass, "wybrano wifi: " + get_curent_position(hass).split(';')[0], None)
    elif CURR_ENTITIE == "input_select.ais_music_service":
        _say_it(hass, "Wybrano " + position + ", jakiej muzyki mam wyszukać", None)
        set_curr_entity(hass, 'input_text.ais_music_query')
        CURR_ENTITIE_ENTERED = True
    else:
        _beep_it(hass, 33)
    # TODO - run the script for the item,
    # the automation on state should be executed only from app not from remote


def set_next_position(hass):
    global CURR_ENTITIE_POSITION
    CURR_ENTITIE_POSITION = get_curent_position(hass)
    state = hass.states.get(CURR_ENTITIE)
    if CURR_ENTITIE.startswith('input_select.'):
        arr = state.attributes.get('options')
        # the "-" option is always first
        if (len(arr) < 2):
            _say_it(hass, "brak pozycji", None)
        else:
            CURR_ENTITIE_POSITION = get_next(arr, CURR_ENTITIE_POSITION)
            if CURR_ENTITIE == "input_select.folder_name":
                if CURR_ENTITIE_POSITION == "..":
                    CURR_ENTITIE_POSITION = get_next(arr, CURR_ENTITIE_POSITION)
                # check if we have remote or local path
                if CURR_ENTITIE_POSITION.startswith(ais_drives_service.G_CLOUD_PREFIX):
                    if CURR_ENTITIE_POSITION == ais_drives_service.G_CLOUD_PREFIX:
                        item = ais_drives_service.G_CLOUD_PREFIX.replace("/", "")
                    else:
                        item = CURR_ENTITIE_POSITION.replace(ais_drives_service.G_CLOUD_PREFIX, "")
                        k = item.find(":")
                        if k+1 < len(item):
                            item = item[k:]
                    _say_it(hass, os.path.basename(item), None)
                else:
                    _say_it(hass, os.path.basename(CURR_ENTITIE_POSITION), None)
            else:
                _say_it(hass, CURR_ENTITIE_POSITION, None)
    elif CURR_ENTITIE.startswith('input_number.'):
        _max = float(state.attributes.get('max'))
        _step = float(state.attributes.get('step'))
        _curr = float(CURR_ENTITIE_POSITION)
        CURR_ENTITIE_POSITION = str(round(min(_curr+_step, _max), 2))
        _say_it(hass, str(CURR_ENTITIE_POSITION), None)


def set_prev_position(hass):
    global CURR_ENTITIE_POSITION
    CURR_ENTITIE_POSITION = get_curent_position(hass)
    state = hass.states.get(CURR_ENTITIE)
    if CURR_ENTITIE.startswith('input_select.'):
        arr = state.attributes.get('options')
        if len(arr) < 2:
            _say_it(hass, "brak pozycji", None)
        else:
            CURR_ENTITIE_POSITION = get_prev(arr, CURR_ENTITIE_POSITION)
            _say_it(hass, CURR_ENTITIE_POSITION, None)
    elif CURR_ENTITIE.startswith('input_number.'):
        _min = float(state.attributes.get('min'))
        _step = float(state.attributes.get('step'))
        _curr = float(CURR_ENTITIE_POSITION)
        CURR_ENTITIE_POSITION = str(round(max(_curr-_step, _min), 2))
        _say_it(hass, str(CURR_ENTITIE_POSITION), None)


def select_entity(hass, long_press):
    # on remote OK, select group view, group or entity
    global CURR_ENTITIE_ENTERED
    # OK on remote
    if CURR_GROUP_VIEW is None:
        # no group view was selected
        set_curr_group_view()
        say_curr_group_view(hass)
        return
    if CURR_GROUP is None:
        # no group is selected - we need to select the first one
        # from the group view
        set_curr_group(hass, None)
        say_curr_group(hass)
        return
    if CURR_ENTITIE is None:
        # no entity is selected - we need to focus the first one
        set_curr_entity(hass, None)
        say_curr_entity(hass)
        CURR_ENTITIE_ENTERED = False
        return

    if CURR_ENTITIE == 'sensor.dyski':
        hass.services.call('ais_drives_service', 'remote_select_item')
        return

    if CURR_ENTITIE_ENTERED is False:
        # check if the entity option can be selected
        if can_entity_be_changed(hass, CURR_ENTITIE):
            if can_entity_be_entered(hass, CURR_ENTITIE):
                CURR_ENTITIE_ENTERED = True
                if CURR_ENTITIE.startswith('input_text.'):
                    _say_it(hass, "Wpisywanie tekstu włączone", None)
                    reset_virtual_keyboard(hass)
                else:
                    set_next_position(hass)
                return
            else:
                # we will change this item directly
                if CURR_ENTITIE.startswith("media_player."):
                    # enter to media player
                    CURR_ENTITIE_ENTERED = True
                    # play / pause on selected player
                    curr_state = hass.states.get(CURR_ENTITIE).state
                    if curr_state == 'playing':
                        if long_press is True:
                            _say_it(hass, "stop", None)
                            hass.services.call('media_player', 'media_stop', {"entity_id": CURR_ENTITIE})
                        else:
                            _say_it(hass, "pauza", None)
                            hass.services.call('media_player', 'media_pause', {"entity_id": CURR_ENTITIE})
                    else:
                        _say_it(hass, "graj", None)
                        hass.services.call('media_player', 'media_play', {"entity_id": CURR_ENTITIE})
                elif CURR_ENTITIE.startswith('input_boolean.'):
                    curr_state = hass.states.get(CURR_ENTITIE).state
                    if curr_state == 'on':
                        _say_it(hass, "ok, wyłączam", None)
                    if curr_state == 'off':
                        _say_it(hass, "ok, włączam", None)
                    hass.services.call(
                        'input_boolean',
                        'toggle', {
                            "entity_id": CURR_ENTITIE})
                elif CURR_ENTITIE.startswith('switch.'):
                    curr_state = hass.states.get(CURR_ENTITIE).state
                    if curr_state == 'on':
                        _say_it(hass, "ok, wyłączam", None)
                    if curr_state == 'off':
                        _say_it(hass, "ok, włączam", None)
                    if curr_state == 'unavailable':
                        _say_it(hass, "przełącznik jest niedostępny", None)
                    hass.services.call(
                        'switch',
                        'toggle', {
                            "entity_id": CURR_ENTITIE})
                elif CURR_ENTITIE.startswith('light.'):
                    curr_state = hass.states.get(CURR_ENTITIE).state
                    if curr_state == 'on':
                        _say_it(hass, "ok, wyłączam", None)
                    elif curr_state == 'off':
                        _say_it(hass, "ok, włączam", None)
                    elif curr_state == 'unavailable':
                        _say_it(hass, "oświetlnie jest niedostępne", None)
                    hass.services.call(
                        'light',
                        'toggle', {
                            "entity_id": CURR_ENTITIE})
                elif CURR_ENTITIE.startswith('script.'):
                    hass.services.call(
                        'script',
                        CURR_ENTITIE.split('.')[1]
                    )

        else:
            # do some special staff for some entries
            if CURR_ENTITIE == 'sensor.version_info':
                # get the info about upgrade
                state = hass.states.get(CURR_ENTITIE)
                upgrade = state.attributes.get('reinstall_dom_app')
                if upgrade is True:
                    _say_it(
                        hass,
                        "Aktualizuje system do najnowszej wersji. Do usłyszenia.", None)
                    hass.services.call('ais_shell_command', 'execute_upgrade')
                else:
                    _say_it(hass, "Twoja wersja jest aktualna", None)
            else:
                _say_it(hass, "Tej pozycji nie można zmieniać", None)

    if CURR_ENTITIE_ENTERED is True:
        # check if we can change this item
        if can_entity_be_changed(hass, CURR_ENTITIE):
            # these items can be controlled from remote
            # if we are here it means that the enter on the same item was
            # pressed twice, we should do something - to mange the item status
            if CURR_ENTITIE.startswith('input_select.'):
                commit_current_position(hass)
            elif CURR_ENTITIE.startswith('input_number.'):
                commit_current_position(hass)
            elif CURR_ENTITIE.startswith("media_player."):
                # play / pause on selected player
                curr_state = hass.states.get(CURR_ENTITIE).state
                if curr_state == 'playing':
                    if long_press is True:
                        _say_it(hass, "stop", None)
                        hass.services.call('media_player', 'media_stop', {"entity_id": CURR_ENTITIE})
                    else:
                        _say_it(hass, "pauza", None)
                        hass.services.call('media_player', 'media_pause', {"entity_id": CURR_ENTITIE})
                else:
                    _say_it(hass, "graj", None)
                    hass.services.call('media_player', 'media_play', {"entity_id": CURR_ENTITIE})
            elif CURR_ENTITIE.startswith('input_text.'):
                type_to_input_text_from_virtual_keyboard(hass)
        else:
            # eneter on unchanged item
            _say_it(hass, "Tej pozycji nie można zmieniać", None)


def can_entity_be_changed(hass, entity):
    # check if entity can be changed
    if CURR_ENTITIE.startswith((
        "media_player.",
        "input_boolean.",
        "switch.",
        "script.",
        "light.",
        "input_text.",
        "input_select.",
        "input_number."
    )):
        return True
    else:
        return False


def can_entity_be_entered(hass, entity):
    # check if entity can be changed
    if CURR_ENTITIE.startswith((
        "media_player.",
        "input_boolean.",
        "switch.",
        "script.",
        "light."
    )):
        return False
    else:
        return True


def set_on_dpad_down(hass, long_press):
    #
    if CURR_ENTITIE is not None:
        if CURR_ENTITIE.startswith("media_player."):
            # speed up on remote
            state = hass.states.get('input_number.media_player_speed')
            _min = float(state.attributes.get('min'))
            _step = float(state.attributes.get('step'))
            _curr = round(max(float(state.state) - _step, _min), 2)
            _say_it(hass, str(_curr), None)
            _LOGGER.info("speed down the player - info from remote: " + str(_curr))
            hass.services.call(
                'ais_ai_service',
                'publish_command_to_frame', {
                    "key": 'setPlaybackSpeed',
                    "val": _curr
                }
            )
            hass.services.call(
                'input_number',
                'set_value', {
                    "entity_id": "input_number.media_player_speed",
                    "value": _curr})
            return
        elif CURR_ENTITIE.startswith('input_text.') and CURR_ENTITIE_ENTERED:
            set_prev_virtual_keyboard_mode()
            say_curr_virtual_keyboard_mode(hass)


def set_on_dpad_up(hass, long_press):
    #
    if CURR_ENTITIE is not None:
        if CURR_ENTITIE.startswith("media_player."):
            # speed up on remote
            state = hass.states.get('input_number.media_player_speed')
            _max = float(state.attributes.get('max'))
            _step = float(state.attributes.get('step'))
            _curr = round(min(float(state.state) + _step, _max), 2)
            _say_it(hass, str(_curr), None)
            _LOGGER.info("speed up the player - info from remote: " + str(_curr))
            hass.services.call(
                'ais_ai_service',
                'publish_command_to_frame', {
                    "key": 'setPlaybackSpeed',
                    "val": _curr
                }
            )
            hass.services.call(
                'input_number',
                'set_value', {
                    "entity_id": "input_number.media_player_speed",
                    "value": _curr})
            return
        elif CURR_ENTITIE.startswith('input_text.') and CURR_ENTITIE_ENTERED:
            set_next_virtual_keyboard_mode()
            say_curr_virtual_keyboard_mode(hass)


def set_focus_on_prev_entity(hass, long_press):
    # prev on joystick
    if long_press and CURR_ENTITIE is not None:
        if CURR_ENTITIE.startswith("media_player."):
            # seek back on remote
            _LOGGER.info("seek back in the player - info from remote")
            hass.services.call('media_player', 'media_seek', {"entity_id": CURR_ENTITIE, "seek_position": 0})
            return
    # no group is selected go to prev in the groups view menu
    if CURR_GROUP is None:
            set_prev_group_view()
            say_curr_group_view(hass)
            return
    # group is selected
    # check if the entity in the group is selected
    if CURR_ENTITIE is None:
            set_prev_group(hass)
            say_curr_group(hass)
            return
    # entity in the group is selected
    # check if the entity option can be selected
    if can_entity_be_changed(hass, CURR_ENTITIE) and CURR_ENTITIE_ENTERED is True:
        if CURR_ENTITIE.startswith("media_player."):
            hass.services.call('media_player', 'media_previous_track', {"entity_id": CURR_ENTITIE})
        elif CURR_ENTITIE.startswith('input_text.') and CURR_ENTITIE_ENTERED:
            set_prev_virtual_key()
            say_curr_virtual_key(hass)
        else:
            set_prev_position(hass)
    else:
        if CURR_ENTITIE.startswith("media_player.") and CURR_ENTITIE_ENTERED:
            hass.services.call('media_player', 'media_previous_track', {"entity_id": CURR_ENTITIE})
        elif CURR_ENTITIE == "sensor.dyski":
            hass.services.call('ais_drives_service', 'remote_prev_item')
        else:
            # entity not selected or no way to change the entity, go to next one
            set_prev_entity(hass)


def set_focus_on_next_entity(hass, long_press):
    # next on joystick
    if long_press and CURR_ENTITIE is not None:
        if CURR_ENTITIE.startswith("media_player."):
            # seek next on remote
            _LOGGER.info("seek next in the player - info from remote")
            hass.services.call('media_player', 'media_seek', {"entity_id": CURR_ENTITIE, "seek_position": 1})
            return
    # no group is selected go to next in the groups view menu
    if CURR_GROUP is None:
            set_next_group_view()
            say_curr_group_view(hass)
            return
    # group is selected
    # check if the entity in the group is selected
    if CURR_ENTITIE is None:
            set_next_group(hass)
            say_curr_group(hass)
            return
    # entity in the group is selected
    # check if the entity option can be selected
    if can_entity_be_changed(hass, CURR_ENTITIE) and CURR_ENTITIE_ENTERED is True:
        if CURR_ENTITIE.startswith("media_player."):
            hass.services.call('media_player', 'media_next_track', {"entity_id": CURR_ENTITIE})
        elif CURR_ENTITIE.startswith('input_text.') and CURR_ENTITIE_ENTERED:
            set_next_virtual_key()
            say_curr_virtual_key(hass)
        else:
            set_next_position(hass)
    else:
        if CURR_ENTITIE.startswith("media_player.") and CURR_ENTITIE_ENTERED is True:
            hass.services.call('media_player', 'media_next_track', {"entity_id": CURR_ENTITIE})
        elif CURR_ENTITIE == "sensor.dyski":
            hass.services.call('ais_drives_service', 'remote_next_item')
        else:
            # entity not selected or no way to change the entity, go to next one
            set_next_entity(hass)


def go_up_in_menu(hass):
    # on back on remote
    global CURR_ENTITIE_ENTERED
    # check if the entity in the group is selected
    if CURR_ENTITIE is not None:
        # check if we are browsing files
        if CURR_ENTITIE == "sensor.dyski":
            # check if we can go up
            state = hass.states.get('sensor.dyski')
            if state.state is not None and state.state != '':
                hass.services.call('ais_drives_service', 'remote_cancel_item')
                return
            else:
                # go up in the group menu
                set_curr_group(hass, None)
                say_curr_group(hass)
        elif not CURR_ENTITIE_ENTERED:
            # go up in the group menu
            set_curr_group(hass, None)
            say_curr_group(hass)
        else:
            CURR_ENTITIE_ENTERED = False
            if CURR_ENTITIE.startswith('input_text.'):
                if CURR_VIRTUAL_KEYBOARD_VALUE is None:
                    hass.services.call('input_text', 'set_value', {
                        "entity_id": CURR_ENTITIE, "value": ""})
                else:
                    hass.services.call('input_text', 'set_value', {
                        "entity_id": CURR_ENTITIE, "value": CURR_VIRTUAL_KEYBOARD_VALUE})
            say_curr_entity(hass)
        return
    # no entity is selected, check if the group is selected
    elif CURR_GROUP is not None:
        # go up in the group view menu
        set_curr_group_view()
        say_curr_group_view(hass)
        return
    # can't go up, beep
    _beep_it(hass, 33)


def type_to_input_text(hass, key):
    if CURR_ENTITIE.startswith('input_text.') and CURR_ENTITIE_ENTERED:
        # add the letter to the virtual input
        global CURR_VIRTUAL_KEYBOARD_VALUE
        if CURR_VIRTUAL_KEYBOARD_VALUE is None:
            CURR_VIRTUAL_KEYBOARD_VALUE = chr(key)
        else:
            CURR_VIRTUAL_KEYBOARD_VALUE = CURR_VIRTUAL_KEYBOARD_VALUE + chr(key)

        _say_it(hass, "wpisano: " + chr(key), None)


def type_to_input_text_from_virtual_keyboard(hass):
    # add the letter to the virtual input
    global CURR_VIRTUAL_KEYBOARD_VALUE
    if CURR_VIRTUAL_KEYBOARD_VALUE is None:
        CURR_VIRTUAL_KEYBOARD_VALUE = ""
    if CURR_VIRTUAL_KEY is None:
        if get_curr_virtual_keyboard_mode() == "Usuwanie":
            _say_it(hass, "wybierz tryb usuwania", None)
        else:
            _say_it(hass, "wybierz znak do wpisania", None)
        return

    key = get_curr_virtual_key()
    km = get_curr_virtual_keyboard_mode()
    if km == "Litery":
        key = key.lower()
    if km == "Usuwanie":
        if key == 'ostatni znak':
            text = CURR_VIRTUAL_KEYBOARD_VALUE[:-1]
        elif key == 'ostatni wyraz':
            text = CURR_VIRTUAL_KEYBOARD_VALUE.rsplit(' ', 1)[0]
        else:
            text = ""
    else:
        text = CURR_VIRTUAL_KEYBOARD_VALUE + key

    CURR_VIRTUAL_KEYBOARD_VALUE = text

    text = ""
    if km == "Litery":
        text = "wpisuję literę: " + key.lower()
    elif km == "Wielkie litery":
        text = "wpisuję wielką literę: " + key
    elif km == "Cyfry":
        text = "wpisuję cyfrę: " + key
    elif km == "Znaki specjalne":
        idx = VIRTUAL_KEYBOARD_SYMBOLS.index(key)
        text = "" + VIRTUAL_KEYBOARD_SYMBOLS_NAMES[idx]
        text = "wpisuję znak: " + text
    elif km == "Usuwanie":
        text = "OK, usuwam " + key

    _say_it(hass, text, None)


def go_to_player(hass, say):
    # selecting the player to control via remote
    global CURR_ENTITIE_ENTERED
    if len(GROUP_ENTITIES) == 0:
        get_groups(hass)
    for group in GROUP_ENTITIES:
        if group['entity_id'] == 'group.audio_player':
            set_curr_group(hass, group)
            set_curr_entity(hass, 'media_player.wbudowany_glosnik')
            CURR_ENTITIE_ENTERED = True
            if say:
                _say_it(hass, "Sterowanie odtwarzaczem", None)


def go_home(hass):
    if len(GROUP_ENTITIES) == 0:
        get_groups(hass)
    global CURR_GROUP_VIEW
    CURR_GROUP_VIEW = 'Twój Dom'
    # to reset
    set_curr_group_view()
    say_curr_group_view(hass)


def get_groups(hass):
    global GROUP_ENTITIES
    global ALL_AIS_SENSORS
    entities = hass.states.async_all()
    GROUP_ENTITIES = []

    def add_menu_item(l_entity):
        l_group = {'friendly_name': l_entity.attributes.get('friendly_name'),
                   'order': l_entity.attributes.get('order'),
                   'entity_id': l_entity.entity_id,
                   'entities': l_entity.attributes.get('entity_id'),
                   'context_key_words': l_entity.attributes.get('context_key_words'),
                   'context_answer': l_entity.attributes.get('context_answer'),
                   'context_suffix': l_entity.attributes.get('context_suffix'),
                   'remote_group_view': l_entity.attributes.get('remote_group_view')}
        GROUP_ENTITIES.append(l_group)

    def getKey(item):
        return item['order']

    for entity in entities:
        if entity.entity_id.startswith('group.'):
            remote = entity.attributes.get('remote_group_view')
            if remote is not None:
                if entity.entity_id != 'group.ais_pilot':
                    add_menu_item(entity)
        elif entity.entity_id.startswith('sensor.'):
            # add sensors to the all_ais_sensors group
            device_class = entity.attributes.get('device_class', None)
            if device_class is not None:
                # new_sensor = {
                #     "entity_id": entity.entity_id,
                #     "friendly_name": entity.attributes.get('friendly_name', "Brak nazwy")}
                # ALL_AIS_SENSORS.append(new_sensor)
                # # sort by name
                # entities = []
                # for sorted_sensors in sorted(ALL_AIS_SENSORS, key=lambda i: i['friendly_name']):
                #     entities.append(sorted_sensors['entity_id'])
                # # distinct
                # entities = list(set(entities))
                ALL_AIS_SENSORS.append(entity.entity_id)
                all_unique_sensors = list(set(ALL_AIS_SENSORS))
                all_unique_sensors.sort()
                hass.async_add_job(
                    hass.services.async_call(
                        'group',
                        'set', {
                            "object_id": "all_ais_sensors",
                            "entities": all_unique_sensors
                        }
                    )
                )
                # update sensors on remote
                for group in GROUP_ENTITIES:
                    if group['entity_id'] == 'group.all_ais_sensors':
                        group['entities'] = tuple(all_unique_sensors)

    GROUP_ENTITIES = sorted(GROUP_ENTITIES, key=getKey)


@asyncio.coroutine
async def async_setup(hass, config):
    """Register the process service."""
    warnings.filterwarnings('ignore', module='fuzzywuzzy')
    config = config.get(DOMAIN, {})
    intents = hass.data.get(DOMAIN)
    if intents is None:
        intents = hass.data[DOMAIN] = {}

    for intent_type, utterances in config.get('intents', {}).items():
        conf = intents.get(intent_type)
        if conf is None:
            conf = intents[intent_type] = []
        conf.extend(_create_matcher(utterance) for utterance in utterances)

    @asyncio.coroutine
    async def process(service):
        """Parse text into commands."""
        text = service.data[ATTR_TEXT]
        callback = None
        if 'callback' in service.data:
            callback = service.data['callback']
        await _process(hass, text, callback)

    def process_code(service):
        """Parse remote code into action."""
        text = json.loads(service.data.get(ATTR_TEXT))
        _process_code(hass, text, None)

    def say_it(service):
        """Info to the user."""
        text = service.data[ATTR_TEXT]
        _say_it(hass, text, None)

    def welcome_home(service):
        """Welcome message."""
        text = "Witaj w Domu. Powiedz proszę w czym mogę Ci pomóc?"
        if ais_global.G_OFFLINE_MODE:
            text = "Uwaga, uruchomienie bez dostępu do sieci, część usług może nie działać poprawnie." \
                   "Sprawdź połączenie z Internetem."
        _say_it(hass, text, None)

    @asyncio.coroutine
    def publish_command_to_frame(service):
        key = service.data['key']
        val = service.data['val']
        ip = 'localhost'
        if "ip" in service.data:
            if service.data['ip'] is not None:
                ip = service.data['ip']
        _publish_command_to_frame(hass, key, val, ip)

    def process_command_from_frame(service):
        _process_command_from_frame(hass, service)

    # fix for the problem on box with remote
    def prepare_remote_menu(service):
        get_groups(hass)
        # register context intent
        for menu in GROUP_ENTITIES:
            context_key_words = menu['context_key_words']
            if context_key_words is not None:
                context_key_words = context_key_words.split(',')
                async_register(hass, INTENT_CHANGE_CONTEXT, context_key_words)

    def on_new_iot_device_selection(service):
        iot = service.data['iot'].lower()
        # the name according to the selected model
        if 'dom_' + ais_global.G_MODEL_SONOFF_S20 in iot:
            info = "Inteligentne gniazdo"
        elif 'dom_' + ais_global.G_MODEL_SONOFF_B1 in iot:
            info = "Żarówka"
        elif 'dom_' + ais_global.G_MODEL_SONOFF_TH in iot:
            info = "Przełącznik z czujnikami"
        elif 'dom_' + ais_global.G_MODEL_SONOFF_SLAMPHER in iot:
            info = "Oprawka"
        elif 'dom_' + ais_global.G_MODEL_SONOFF_TOUCH in iot:
            info = "Przełącznik dotykowy"
        elif 'dom_' + ais_global.G_MODEL_SONOFF_POW in iot:
            info = "Przełącznik z pomiarem mocy"
        elif 'dom_' + ais_global.G_MODEL_SONOFF_DUAL in iot:
            info = "Przełącznik podwójny"
        elif 'dom_' + ais_global.G_MODEL_SONOFF_BASIC in iot:
            info = "Przełącznik"
        elif 'dom_' + ais_global.G_MODEL_SONOFF_IFAN in iot:
            info = "Wentylator sufitowy"
        elif 'dom_' + ais_global.G_MODEL_SONOFF_T11 in iot:
            info = "Przełącznik dotykowy pojedynczy"
        elif 'dom_' + ais_global.G_MODEL_SONOFF_T12 in iot:
            info = "Przełącznik dotykowy podwójny"
        elif 'dom_' + ais_global.G_MODEL_SONOFF_T13 in iot:
            info = "Przełącznik dotykowy potrójny"
        else:
            info = "Nowe urządzenie"
        hass.services.call(
            'input_text',
            'set_value', {
                "entity_id": "input_text.ais_iot_device_name",
                "value": info})
        # set the WIFI as an current WIFI (only if empty)
        wifis = hass.states.get('input_select.ais_android_wifi_network')
        if wifis.state == ais_global.G_EMPTY_OPTION and ais_global.GLOBAL_MY_SSID is not None:
            options = wifis.attributes.get('options')
            for o in options:
                if ais_global.GLOBAL_MY_SSID in o:
                    hass.services.call(
                        'input_select',
                        'select_option', {
                            "entity_id": "input_select.ais_android_wifi_network",
                            "option": o})
        # TODO Set the WIFI password if possible

    # register services
    hass.services.async_register(DOMAIN, 'process', process)
    hass.services.async_register(DOMAIN, 'process_code', process_code)
    hass.services.async_register(DOMAIN, 'say_it', say_it)
    hass.services.async_register(DOMAIN, 'welcome_home', welcome_home)
    hass.services.async_register(DOMAIN, 'publish_command_to_frame', publish_command_to_frame)
    hass.services.async_register(DOMAIN, 'process_command_from_frame', process_command_from_frame)
    hass.services.async_register(DOMAIN, 'prepare_remote_menu', prepare_remote_menu)
    hass.services.async_register(DOMAIN, 'on_new_iot_device_selection', on_new_iot_device_selection)

    hass.helpers.intent.async_register(GetTimeIntent())
    hass.helpers.intent.async_register(GetDateIntent())
    hass.helpers.intent.async_register(AisClimateSetTemperature())
    hass.helpers.intent.async_register(AisClimateSetAway())
    hass.helpers.intent.async_register(AisClimateUnSetAway())
    hass.helpers.intent.async_register(AisClimateSetAllOn())
    hass.helpers.intent.async_register(AisClimateSetAllOff())
    hass.helpers.intent.async_register(TurnOnIntent())
    hass.helpers.intent.async_register(TurnOffIntent())
    hass.helpers.intent.async_register(StatusIntent())
    hass.helpers.intent.async_register(PlayRadioIntent())
    hass.helpers.intent.async_register(AisPlayPodcastIntent())
    hass.helpers.intent.async_register(AisPlayYtMusicIntent())
    hass.helpers.intent.async_register(AisPlaySpotifyIntent())
    hass.helpers.intent.async_register(AskQuestionIntent())
    hass.helpers.intent.async_register(ChangeContextIntent())
    hass.helpers.intent.async_register(AisGetWeather())
    hass.helpers.intent.async_register(AisGetWeather48())
    hass.helpers.intent.async_register(AisLampsOn())
    hass.helpers.intent.async_register(AisLampsOff())
    hass.helpers.intent.async_register(AisSwitchesOn())
    hass.helpers.intent.async_register(AisSwitchesOff())
    hass.helpers.intent.async_register(AisOpenCover())
    hass.helpers.intent.async_register(AisCloseCover())
    hass.helpers.intent.async_register(AisStop())
    hass.helpers.intent.async_register(AisPlay())
    hass.helpers.intent.async_register(AisNext())
    hass.helpers.intent.async_register(AisPrev())
    hass.helpers.intent.async_register(AisSceneActive())
    hass.helpers.intent.async_register(AisSayIt())

    async_register(hass, INTENT_GET_WEATHER, [
            '[aktualna] pogoda',
            'pogoda w {location}',
            'pogoda we {location}',
            'jaka jest pogoda',
            'jaka jest pogoda w {location}',
            'jaka jest pogoda we {location}'
    ])
    async_register(hass, INTENT_GET_WEATHER_48, [
            'prognoza pogody',
            'pogoda prognoza',
            'pogoda jutro',
            'pogoda jutro w {location}',
            'pogoda jutro we {location}',
            'jaka będzie pogoda',
            'jaka będzie pogoda w {location}'
    ])
    async_register(hass, INTENT_CLIMATE_SET_TEMPERATURE, [
        "Ustaw temperaturę [ogrzewania] [na] {temp} stopni [w] {item} ",
        "Temperatura ogrzewania {temp} stopni [w] {item}",
        "Temperatura ogrzewania [w] {item} {temp} stopni",
        "Ogrzewanie [w] {item} temperatura {temp} stopni",
        "Ogrzewanie temperatura w {item} {temp} stopni"])
    async_register(hass, INTENT_CLIMATE_SET_AWAY, [
        "Ogrzewanie [na] [w] [tryb] poza domem", "Ogrzewanie włącz [tryb] poza domem"])
    async_register(hass, INTENT_CLIMATE_UNSET_AWAY, [
        "Ogrzewanie [na] [w] [tryb] w domu", "Ogrzewanie wyłącz [tryb] poza domem"])
    async_register(hass, INTENT_CLIMATE_SET_ALL_OFF, ["Wyłącz całe ogrzewnie", "Wyłącz ogrzewnie"])
    async_register(hass, INTENT_CLIMATE_SET_ALL_ON, ["Włącz całe ogrzewnie", "Włącz ogrzewnie"])
    async_register(hass, INTENT_LAMPS_ON, [
            'włącz światła',
            'zapal światła',
            'włącz wszystkie światła',
            'zapal wszystkie światła'
    ])
    async_register(hass, INTENT_LAMPS_OFF, [
            'zgaś światła',
            'wyłącz światła',
            'wyłącz wszystkie światła',
            'zgaś wszystkie światła'
    ])
    async_register(hass, INTENT_SWITCHES_ON, [
            'włącz przełączniki',
            'włącz wszystkie przełączniki'
    ])
    async_register(hass, INTENT_SWITCHES_OFF, [
            'wyłącz przełączniki',
            'wyłącz wszystkie przełączniki'
    ])
    async_register(hass, INTENT_GET_TIME, [
            'która [jest] [teraz] godzina',
            'którą mamy godzinę',
            'jaki [jest] czas',
            '[jaka] [jest] godzina',
    ])
    async_register(hass, INTENT_GET_DATE, [
            '[jaka] [jest] data',
            'jaki [mamy] [jest] [dzisiaj] dzień',
            'co dzisiaj jest',
            'co [mamy] [jest] dzisiaj',
    ])
    async_register(hass, INTENT_PLAY_RADIO, [
        'Radio {item}',
        'Włącz radio {item}',
        'Graj radio {item}',
        'Graj {item} radio',
        'Przełącz [na] radio [na] {item}',
        'Posłuchał bym radio {item}',
        'Włącz stację radiową {item}',
    ])
    async_register(hass, INTENT_PLAY_PODCAST, [
        'Podcast {item}',
        'Włącz podcast {item}',
        'Graj podcast {item}',
        'Graj {item} podcast',
        'Przełącz [na] podcast {item}',
        'Posłuchał bym podcast {item}',
    ])
    async_register(hass, INTENT_PLAY_YT_MUSIC, [
        'Muzyka {item}',
        'Włącz muzykę {item}',
        'Graj muzykę {item}',
        'Graj {item} muzykę',
        'Przełącz [na] muzykę [na] {item}',
        'Posłuchał bym muzykę {item}',
        'Włącz [z] [na] YouTube {item}',
        'YouTube {item}'
    ])
    async_register(hass, INTENT_PLAY_SPOTIFY, [
        'Spotify {item}'
    ])
    async_register(hass, INTENT_TURN_ON,
                   ['Włącz {item}', 'Zapal światło w {item}'])
    async_register(hass, INTENT_TURN_OFF,
                   ['Wyłącz {item}', 'Zgaś Światło w {item}'])
    async_register(hass, INTENT_STATUS, [
        'Jaka jest {item}', 'Jaki jest {item}',
        'Jak jest {item}', 'Jakie jest {item}',
        '[jaki] [ma] status {item}'])
    async_register(hass, INTENT_ASK_QUESTION, [
        'Co to jest {item}', 'Kto to jest {item}',
        'Znajdź informację o {item}', 'Znajdź informacje o {item}',
        'Wyszukaj informację o {item}', 'Wyszukaj informacje o {item}',
        'Wyszukaj {item}', 'Kim jest {item}', 'Informacje o {item}',
        'Czym jest {item}', 'Opowiedz mi o {intem}',
        'Informację na temat {item}', 'Co wiesz o {item}',
        'Co wiesz na temat {item}', 'Opowiedz o {item}',
        'Kim są {item}', 'Kto to {item}'])
    async_register(hass, INTENT_OPEN_COVER, ['Otwórz {item}', 'Odsłoń {item}'])
    async_register(hass, INTENT_CLOSE_COVER, ['Zamknij {item}', 'Zasłoń {item}'])
    async_register(hass, INTENT_STOP, ['Stop', 'Zatrzymaj', 'Koniec', 'Pauza', 'Zaniechaj', 'Stój'])
    async_register(hass, INTENT_PLAY, ['Start', 'Graj', 'Odtwarzaj'])
    async_register(hass, INTENT_SCENE, ['Scena {item}', 'Aktywuj [scenę] {item}'])
    async_register(hass, INTENT_NEXT, ['[włącz] następny', '[włącz] kolejny', '[graj] następny', '[graj] kolejny'])
    async_register(hass, INTENT_PREV, ['[włącz] poprzedni', '[włącz] wcześniejszy', '[graj] poprzedni',
                                       '[graj] wcześniejszy'])
    async_register(hass, INTENT_SAY_IT, ['Powiedz', 'Mów', 'Powiedz {item}', 'Mów {item}', 'Echo {item}'])

    return True


def _publish_command_to_frame(hass, key, val, ip):
    # sent the command to the android frame via http
    url = G_HTTP_REST_SERVICE_BASE_URL.format(ip)

    if key == "WifiConnectToSid":
        # enable the wifi info
        hass.async_run_job(
            hass.services.async_call(
                'input_boolean',
                'input_boolean',
                'turn_on', {"entity_id": "input_boolean.ais_android_wifi_changes_notify"})
        )
        ssid = val.split(';')[0]
        if ssid is None or ssid == "-" or ssid == "":
            _say_it(hass, "Wybierz sieć WiFi z listy", None)
            return


        # TODO get password from file
        password = hass.states.get('input_text.ais_android_wifi_password').state
        if len(password.strip()) == 0:
            _say_it(hass, "ok, przełączam na sieć: " + ssid, None)
        else:
            _say_it(hass, "ok, łączę z siecią: " + ssid, None)

        wifi_type = val.split(';')[-3]
        bssid = val.split(';')[-1].replace("MAC:", "").strip()
        requests.post(
            url + '/command',
            json={key: ssid, "ip": ip, "WifiNetworkPass": password, "WifiNetworkType": wifi_type, "bssid": bssid},
            timeout=2)

    elif key == "WifiConnectTheDevice":
        iot = val.split(';')[0]
        if iot == ais_global.G_EMPTY_OPTION:
            _say_it(hass, "wybierz wifi do której mam dołączyć urządzenie", None)
            return
        # check if wifi is selected
        ssid = hass.states.get('input_select.ais_android_wifi_network').state.split(';')[0]
        if ssid == ais_global.G_EMPTY_OPTION:
            _say_it(hass, "wybierz wifi do której mam dołączyć urządzenie", None)
            return

        # take bssid
        bssid = val.split(';')[-1].replace("MAC:", "").strip()

        # check the frequency
        wifi_frequency_mhz = val.split(';')[-2]
        if not wifi_frequency_mhz.startswith("2.4"):
            _say_it(hass, "Urządzenia mogą pracować tylko w sieci 2.4 GHz, wybierz inną sieć.", None)

        # check if name is selected, if not then add the device name
        name = hass.states.get('input_text.ais_iot_device_name').state
        # friendly name (32 chars max)
        if name == "":
            name = iot
        if len(name) > 32:
            _say_it(hass, "nazwa urządzenie może mieć maksymalnie 32 znaki", None)
            return
        _say_it(hass, "dodajemy: " + name, None)
        password = hass.states.get('input_text.ais_iot_device_wifi_password').state

        requests.post(
            url + '/command',
            json={key: iot, "ip": ip, "WifiNetworkPass": password, "WifiNetworkSsid": ssid,
                  "IotName": name, "bsssid": bssid},
            timeout=2)
    else:
        try:
            requests.post(
                url + '/command',
                json={key: val, "ip": ip},
                timeout=2)
        except Exception as e:
            _LOGGER.info(
                "_publish_command_to_frame requests.post problem key: "
                + str(key) + " val: " + str(val) + " ip " + str(ip) + str(e))


def _wifi_rssi_to_info(rssi):
    info = "moc nieznana"
    if rssi > -31:
        return "moc doskonała (" + str(rssi) + ")"
    if rssi > -68:
        return "moc bardzo dobra (" + str(rssi) + ")"
    if rssi > -71:
        return "moc dobra (" + str(rssi) + ")"
    if rssi > -81:
        return "moc słaba (" + str(rssi) + ")"
    if rssi > -91:
        return "moc bardzo słaba (" + str(rssi) + ")"
    return info


def _wifi_frequency_info(mhz):
    if str(mhz).startswith("2"):
        return "2.4 GHz"
    elif str(mhz).startswith("5"):
        return "5 GHz"
    return str(mhz)


def _publish_wifi_status(hass, service):
    wifis = json.loads(service.data["payload"])
    wifis_names = [ais_global.G_EMPTY_OPTION]
    for item in wifis["ScanResult"]:
        if len(item["ssid"]) > 0:
            wifis_names.append(
                item["ssid"] + "; " +
                _wifi_rssi_to_info(item["rssi"]) +
                "; " + item["capabilities"] + "; " + _wifi_frequency_info(item["frequency_mhz"]) +
                "; MAC: " + item["bssid"])
    hass.async_run_job(
        hass.services.call(
            'input_select',
            'set_options', {
                "entity_id": "input_select.ais_android_wifi_network",
                "options": wifis_names})
    )
    return len(wifis_names)-1


def _process_command_from_frame(hass, service):
    # process from frame
    _LOGGER.info('_process_command_from_frame: ' + str(service.data))
    if "web_hook_json" in service.data:
        import ast
        service.data = ast.literal_eval(service.data["web_hook_json"])
    callback = None
    if "callback" in service.data:
        callback = service.data["callback"]
    if service.data["topic"] == 'ais/speech_command':
        hass.async_run_job(
            _process(hass, service.data["payload"], callback)
        )
        return
    elif service.data["topic"] == 'ais/key_command':
        _process_code(hass, json.loads(service.data["payload"]), callback)
        return
    elif service.data["topic"] == 'ais/speech_text':
        _say_it(hass, service.data["payload"], callback)
        return
    elif service.data["topic"] == 'ais/speech_status':
        # TODO pause/resume, service.data["payload"] can be: START -> DONE/ERROR
        _LOGGER.info('speech_status: ' + str(service.data["payload"]))
        return
    elif service.data["topic"] == 'ais/add_bookmark':
        _LOGGER.info('add_bookmark: ' + str(service.data["payload"]))
        try:
            bookmark = json.loads(service.data["payload"])
            if bookmark["media_source"] != ais_global.G_AN_LOCAL:
                return
            hass.async_run_job(
                hass.services.call('ais_bookmarks',
                                   'add_bookmark',
                                   {"attr":
                                    {"media_title": bookmark["media_title"],
                                     "source": bookmark["media_source"],
                                     "media_position": bookmark["media_position"],
                                     "media_content_id": bookmark["media_content_id"],
                                     "media_stream_image": bookmark["media_stream_image"]}})
            )
        except Exception as e:
            _LOGGER.info("problem to add_bookmark: " + str(e))
        return
    elif service.data["topic"] == 'ais/player_speed':
        speed = json.loads(service.data["payload"])
        # _say_it(hass, "prędkość odtwarzania: " + str(speed["currentSpeed"]), callback)
        # hass.services.call(
        #     'input_number',
        #     'set_value', {
        #         "entity_id": "input_number.media_player_speed",
        #         "value": round(speed["currentSpeed"], 2)})
        return
    elif service.data["topic"] == 'ais/wifi_scan_info':
        len_wifis = _publish_wifi_status(hass, service)
        info = "Mamy dostępne " + str(len_wifis) + " wifi."
        _say_it(hass, info, callback)
        return
    elif service.data["topic"] == 'ais/iot_scan_info':
        iot = json.loads(service.data["payload"])
        iot_names = [ais_global.G_EMPTY_OPTION]
        for item in iot["ScanResult"]:
            if len(item["ssid"]) > 0:
                iot_names.append(
                    item["ssid"] + "; " +
                    _wifi_rssi_to_info(item["rssi"]) +
                    "; " + item["capabilities"])
        hass.async_run_job(
            hass.services.call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.ais_iot_devices_in_network",
                    "options": iot_names})
        )
        if len(iot_names) == 1:
            info = "Nie znaleziono żadnego nowego urządzenia"
        elif len(iot_names) == 2:
            if item["model"] == ais_global.G_MODEL_SONOFF_S20:
                info = "Znaleziono nowe inteligentne gniazdo"
            elif item["model"] == ais_global.G_MODEL_SONOFF_SLAMPHER:
                info = "Znaleziono nową oprawkę"
            elif item["model"] == ais_global.G_MODEL_SONOFF_TOUCH:
                info = "Znaleziono nowy przełącznik dotykowy"
            elif item["model"] == ais_global.G_MODEL_SONOFF_TH:
                info = "Znaleziono nowy przełącznik z czujnikami"
            elif item["model"] == ais_global.G_MODEL_SONOFF_B1:
                info = "Znaleziono nową żarówkę"
            elif item["model"] == ais_global.G_MODEL_SONOFF_POW:
                info = "Znaleziono nowy przełącznik z pomiarem mocy"
            elif item["model"] == ais_global.G_MODEL_SONOFF_DUAL:
                info = "Znaleziono nowy podwójny przełącznik"
            elif item["model"] == ais_global.G_MODEL_SONOFF_BASIC:
                info = "Znaleziono nowy przełącznik"
            elif item["model"] == ais_global.G_MODEL_SONOFF_IFAN:
                info = "Znaleziono nowy wentylator sufitowy"
            elif item["model"] == ais_global.G_MODEL_SONOFF_T11:
                info = "Znaleziono nowy przełącznik dotykowy pojedynczy"
            elif item["model"] == ais_global.G_MODEL_SONOFF_T12:
                info = "Znaleziono nowy przełącznik dotykowy podwójny"
            elif item["model"] == ais_global.G_MODEL_SONOFF_T13:
                info = "Znaleziono nowy przełącznik dotykowy potrójny"
            else:
                info = "Znaleziono nowe urządzenie, to urządzenie może"
                info += " nie być w pełni wspierane przez system 'Asystent domowy'"
        else:
            info = "Znaleziono " + str(len(iot_names)-1) + " nowe urządzenia."
        _say_it(hass, info, callback)
        return
    elif service.data["topic"] == 'ais/wifi_status_info':
        _publish_wifi_status(hass, service)
        return
    elif service.data["topic"] == 'ais/wifi_connection_info':
        # current connection info
        cci = json.loads(service.data["payload"])
        info = " "
        if "ssid" in cci:
            ais_global.set_my_ssid(cci["ssid"])
            if cci["ssid"] == "<unknown ssid>":
                info += "brak połączenia"
            else:
                info += cci["ssid"]
                if "link_speed_mbps" in cci:
                    info += "; prędkość: " + str(cci["link_speed_mbps"]) + " megabitów na sekundę"
                if "rssi" in cci:
                    info += "; " + _wifi_rssi_to_info(cci["rssi"])
                if "frequency_mhz" in cci:
                    info += "; " + _wifi_frequency_info(cci["frequency_mhz"])

        hass.states.async_set(
            'sensor.ais_android_wifi_current_network_info', info, {"friendly_name": "Połączenie Wifi"})
        return
    elif service.data["topic"] == 'ais/wifi_state_change_info':
        # current connection info
        cci = json.loads(service.data["payload"])
        ais_global.set_my_ssid(cci["ssid"])
        info = "Wifi: "
        if "ssid" in cci:
            if 'dom_' + ais_global.G_MODEL_SONOFF_S20 in cci["ssid"].lower():
                info += "gniazdo "
            elif 'dom_' + ais_global.G_MODEL_SONOFF_B1 in cci["ssid"].lower():
                info += "żarówka "
            elif 'dom_' + ais_global.G_MODEL_SONOFF_TH in cci["ssid"].lower():
                info += "przełącznik z czujnikami "
            elif 'dom_' + ais_global.G_MODEL_SONOFF_SLAMPHER in cci["ssid"].lower():
                info += "oprawka "
            elif 'dom_' + ais_global.G_MODEL_SONOFF_TOUCH in cci["ssid"].lower():
                info += "przełącznik dotykowy "
            elif 'dom_' + ais_global.G_MODEL_SONOFF_POW in cci["ssid"].lower():
                info += "przełącznik z pomiarem mocy"
            elif 'dom_' + ais_global.G_MODEL_SONOFF_DUAL in cci["ssid"].lower():
                info += "podwójny przełącznik"
            elif 'dom_' + ais_global.G_MODEL_SONOFF_BASIC in cci["ssid"].lower():
                info += "przełącznik"
            elif 'dom_' + ais_global.G_MODEL_SONOFF_IFAN in cci["ssid"].lower():
                info += "wentylator sufitowy"
            elif 'dom_' + ais_global.G_MODEL_SONOFF_T11 in cci["ssid"].lower():
                info = "przełącznik dotykowy pojedynczy"
            elif 'dom_' + ais_global.G_MODEL_SONOFF_T12 in cci["ssid"].lower():
                info = "przełącznik dotykowy podwójny"
            elif 'dom_' + ais_global.G_MODEL_SONOFF_T13 in cci["ssid"].lower():
                info = "przełącznik dotykowy potrójny"
            else:
                info += cci["ssid"] + " "
        if "state" in cci:
            info += cci["state"]
        # check if we are now online
        if ais_global.GLOBAL_MY_IP == "127.0.0.1":
            ais_global.set_global_my_ip()
            if ais_global.GLOBAL_MY_IP != "127.0.0.1":
                pass
                # if yes then try to reload the cloud and other components
                # TODO reload invalid components
                # hass.async_run_job(async_load_platform(hass, 'sun', 'sun', {}, {}))
                # hass.async_run_job(async_load_platform(hass, 'ais_cloud', 'ais_cloud', {}, {}))
                # hass.async_run_job(async_load_platform(hass, 'ais_yt_service', 'ais_yt_service', {}, {}))
                # hass.async_run_job(async_load_platform(hass, 'ais_knowledge_service', 'ais_knowledge_service'...
        state = hass.states.get('input_boolean.ais_android_wifi_changes_notify').state
        if state == 'on':
            _say_it(hass, info, callback)
        return
    elif service.data["topic"] == 'ais/go_to_player':
        go_to_player(hass, False)
    else:
        # TODO process this without mqtt
        # player_status and speech_status
        mqtt.async_publish(
            hass, service.data["topic"], service.data["payload"], 2)
        # TODO
    return


def _post_message(message, hosts):
    """Post the message to TTS service."""
    message = message.replace("°C", "stopni Celsjusza")
    j_data = {
            "text": message,
            "pitch": ais_global.GLOBAL_TTS_PITCH,
            "rate": ais_global.GLOBAL_TTS_RATE,
            "voice": ais_global.GLOBAL_TTS_VOICE
            }
    for h in hosts:
        _LOGGER.info("sending text_to_speech to: " + str(h))
        try:
            requests.post(
                G_HTTP_REST_SERVICE_BASE_URL.format(h) + '/text_to_speech',
                json=j_data,
                timeout=1
            )
        except Exception as e:
            _LOGGER.info("problem to send the text to speech via http: " + str(e))


def _beep_it(hass, tone):
    """Post the beep to Android frame."""
    # https://android.googlesource.com/platform/frameworks/base/+/b267554/media/java/android/media/ToneGenerator.java
    hass.services.call(
        'ais_ai_service',
        'publish_command_to_frame', {
            "key": 'tone',
            "val": tone
        }
    )


def _say_it(hass, message, caller_ip=None):
    # sent the tts message to the panel via http api
    global GLOBAL_TTS_TEXT
    l_hosts = ['localhost']

    # check if we should inform other speaker
    player_name = hass.states.get('input_select.tts_player').state
    device_ip = None
    if player_name is not None:
        device = ais_cloud.get_player_data(player_name)
        if device is not None:
            device_ip = device["device_ip"]
            if device_ip not in ['localhost', '127.0.0.1']:
                l_hosts.append(device_ip)

    # check if we should inform back the caller speaker
    # the local caller has ip like 192.168.1.45
    # internal_ip = hass.states.get('sensor.internal_ip_address').state
    if ais_global.GLOBAL_MY_IP is None:
        ais_global.set_global_my_ip()
    if caller_ip is not None:
        if caller_ip not in ['localhost', '127.0.0.1', device_ip, ais_global.GLOBAL_MY_IP]:
            l_hosts.append(caller_ip)

    _post_message(message, l_hosts)

    if len(message) > 199:
        GLOBAL_TTS_TEXT = message[0: 199] + '...'
    else:
        GLOBAL_TTS_TEXT = message
    hass.states.async_set(
        'sensor.ais_knowledge_answer', 'ok', {
            'text': GLOBAL_TTS_TEXT
            })


def _create_matcher(utterance):
    """Create a regex that matches the utterance."""
    # Split utterance into parts that are type: NORMAL, GROUP or OPTIONAL
    # Pattern matches (GROUP|OPTIONAL): Change light to [the color] {item}
    parts = re.split(r'({\w+}|\[[\w\s]+\] *)', utterance)
    # Pattern to extract name from GROUP part. Matches {item}
    group_matcher = re.compile(r'{(\w+)}')
    # Pattern to extract text from OPTIONAL part. Matches [the color]
    optional_matcher = re.compile(r'\[([\w ]+)\] *')

    pattern = ['^']
    for part in parts:
        group_match = group_matcher.match(part)
        optional_match = optional_matcher.match(part)

        # Normal part
        if group_match is None and optional_match is None:
            pattern.append(part)
            continue

        # Group part
        if group_match is not None:
            pattern.append(
                r'(?P<{}>[\w ]+?)\s*'.format(group_match.groups()[0]))

        # Optional part
        elif optional_match is not None:
            pattern.append(r'(?:{} *)?'.format(optional_match.groups()[0]))

    pattern.append('$')
    return re.compile(''.join(pattern), re.I)


def _process_code(hass, data, callback):
    """Process a code from remote."""
    global CURR_BUTTON_CODE
    global CURR_BUTTON_LONG_PRESS
    global CURR_ENTITIE_ENTERED
    if 'Action' not in data or 'KeyCode' not in data:
        return
    # check if we have callback
    if callback is not None:
        # TODO the answer should go to the correct clien
        pass

    action = data["Action"]
    code = data["KeyCode"]

    # fix - when the mouse mode on remote is on, the remote is sending only the code 23 (OK) as key down (action 0)
    # to handle this we are ignoring the key up (action 1), and key down (action 0) is changing to key up (action 1)
    if code == 23:
        if action == 1:
            return
        else:
            action = 1

    # ACTION_DOWN = 0; ACTION_UP = 1;
    if action == 0:
        CURR_BUTTON_LONG_PRESS = False
        if "RepeatCount" in data:
            if data["RepeatCount"] > 0:
                CURR_BUTTON_LONG_PRESS = True
        if CURR_BUTTON_LONG_PRESS is False:
            return

    elif action == 2:
        # ACTION_MULTIPLE = 2;
        # check if long press will be send to us
        _LOGGER.info("long press on " + str(data))
        return

    elif action == 1:
        # ACTION_UP
        # to prevent up action after long press
        if CURR_BUTTON_LONG_PRESS is True:
            CURR_BUTTON_LONG_PRESS = False
            return

    _LOGGER.info("KeyCode: -> " + str(code))
    # set the code in global variable
    CURR_BUTTON_CODE = code
    # show the code in web app
    hass.states.set('binary_sensor.ais_remote_button', code)
    # decode Key Events
    # codes according to android.view.KeyEvent
    if code == 93:
        # PG- -> KEYCODE_PAGE_DOWN
        set_bookmarks_curr_group(hass)
        set_curr_entity(hass, 'input_select.ais_bookmark_last_played')
        CURR_ENTITIE_ENTERED = True
        say_curr_entity(hass)
    elif code == 92:
        # PG+ -> KEYCODE_PAGE_UP
        set_bookmarks_curr_group(hass)
        CURR_ENTITIE_ENTERED = True
        set_curr_entity(hass, 'input_select.ais_bookmark_favorites')

        say_curr_entity(hass)
    elif code == 4:
        # Back arrow, go up in menu/groups -> KEYCODE_BACK
        # or go up in local folder structure
        go_up_in_menu(hass)
    elif code == 82:
        # Menu -> KEYCODE_MENU
        set_next_group_view()
        say_curr_group_view(hass)
    elif code == 164:
        # Mute -> KEYCODE_VOLUME_MUTE
        pass
    elif code == 71:
        # MIC DOWN -> KEYCODE_LEFT_BRACKET
        pass
    elif code == 72:
        # MIC UP -> KEYCODE_RIGHT_BRACKET
        pass
    elif code == 19:
        # Dpad up -> KEYCODE_DPAD_UP
        set_on_dpad_up(hass, CURR_BUTTON_LONG_PRESS)
        pass
    elif code == 20:
        # Dpad down -> KEYCODE_DPAD_DOWN
        set_on_dpad_down(hass, CURR_BUTTON_LONG_PRESS)
        pass
    elif code == 21:
        # Dpad left -> KEYCODE_DPAD_LEFT
        set_focus_on_prev_entity(hass, CURR_BUTTON_LONG_PRESS)
    elif code == 22:
        # Dpad right -> KEYCODE_DPAD_RIGHT
        set_focus_on_next_entity(hass, CURR_BUTTON_LONG_PRESS)
    elif code == 23:
        # Dpad center -> KEYCODE_DPAD_CENTER
        select_entity(hass, CURR_BUTTON_LONG_PRESS)
    elif code == 25:
        # Volume down -> KEYCODE_VOLUME_DOWN
        pass
    elif code == 24:
        # Volume up -> KEYCODE_VOLUME_UP
        pass
    elif code == 190:
        # go home -> KEYCODE_HOME
        if CURR_BUTTON_LONG_PRESS:
            go_to_player(hass, True)
        else:
            go_home(hass)
    # other code on text field
    else:
        type_to_input_text(hass, code)


def get_context_suffix(hass):
    context_suffix = GROUP_ENTITIES[get_curr_group_idx()]['context_suffix']
    if context_suffix == 'Muzyka':
        context_suffix = hass.states.get("input_select.ais_music_service").state
    return context_suffix


@asyncio.coroutine
def _process(hass, text, callback):
    """Process a line of text."""
    _LOGGER.info('Process text: ' + text)
    # clear text
    text = text.replace("&", " and ").lower()
    global CURR_BUTTON_CODE
    s = False
    m = None
    m_org = None
    found_intent = None
    # first check the conversation intents
    conv_intents = hass.data.get('conversation', {})
    for intent_type, matchers in conv_intents.items():
        for matcher in matchers:
            match = matcher.match(text)
            if not match:
                continue
            response = yield from hass.helpers.intent.async_handle(
                'conversation', intent_type,
                {key: {'value': value} for key, value
                 in match.groupdict().items()}, text)
            return response

    # check the AIS dom intents
    intents = hass.data.get(DOMAIN, {})
    try:
        for intent_type, matchers in intents.items():
            if found_intent is not None:
                break
            for matcher in matchers:
                match = matcher.match(text)
                if match:
                    # we have a match
                    found_intent = intent_type
                    m, s = yield from hass.helpers.intent.async_handle(
                        DOMAIN, intent_type,
                        {key: {'value': value} for key, value
                         in match.groupdict().items()}, text)
                    break
        # the item was match as INTENT_TURN_ON but we don't have such device - maybe it is radio or podcast???
        if s is False and found_intent == INTENT_TURN_ON:
            m_org = m
            m, s = yield from hass.helpers.intent.async_handle(
                DOMAIN, INTENT_PLAY_RADIO,
                {key: {'value': value} for key, value
                 in match.groupdict().items()}, text.replace("włącz", "włącz radio"))
            if s is False:
                m, s = yield from hass.helpers.intent.async_handle(
                    DOMAIN, INTENT_PLAY_PODCAST,
                    {key: {'value': value} for key, value
                     in match.groupdict().items()}, text.replace("włącz", "włącz podcast"))
            if s is False:
                m = m_org
        # the item was match as INTENT_TURN_ON but we don't have such device - maybe it is climate???
        if s is False and found_intent == INTENT_TURN_ON  and "ogrzewanie" in text:
            m_org = m
            m, s = yield from hass.helpers.intent.async_handle(
                DOMAIN, INTENT_CLIMATE_SET_ALL_ON,
                {key: {'value': value} for key, value
                    in match.groupdict().items()}, text)
            if s is False:
                m = m_org
        # the item was match as INTENT_TURN_OFF but we don't have such device - maybe it is climate???
        if s is False and found_intent == INTENT_TURN_OFF and "ogrzewanie" in text:
            m_org = m
            m, s = yield from hass.helpers.intent.async_handle(
                DOMAIN, INTENT_CLIMATE_SET_ALL_OFF,
                {key: {'value': value} for key, value
                    in match.groupdict().items()}, text)
            if s is False:
                m = m_org
        # the was no match - try again but with current context
        if found_intent is None:
            suffix = get_context_suffix(hass)
            if suffix is not None:
                for intent_type, matchers in intents.items():
                    if found_intent is not None:
                        break
                    for matcher in matchers:
                        match = matcher.match(suffix + " " + text)
                        if match:
                            # we have a match
                            found_intent = intent_type
                            m, s = yield from hass.helpers.intent.async_handle(
                                DOMAIN, intent_type,
                                {key: {'value': value} for key, value
                                 in match.groupdict().items()},
                                suffix + " " + text)
                            # reset the curr button code
                            # TODO the mic should send a button code too
                            # in this case we will know if the call source
                            CURR_BUTTON_CODE = 0
                            break

        # the was no match - try again but with player context
        # we should get media player source first
        if found_intent is None:
            if CURR_ENTITIE == 'media_player.wbudowany_glosnik' and CURR_ENTITIE_ENTERED:
                state = hass.states.get(CURR_ENTITIE)
                if "source" in state.attributes:
                    suffix = ""
                    source = state.attributes.get('source')
                    if source == ais_global.G_AN_MUSIC:
                        suffix = 'youtube'
                    elif source == ais_global.G_AN_RADIO:
                        suffix = 'radio'
                    elif source == ais_global.G_AN_PODCAST:
                        suffix = 'podcast'
                    if suffix != "":
                        for intent_type, matchers in intents.items():
                            if found_intent is not None:
                                break
                            for matcher in matchers:
                                match = matcher.match(suffix + " " + text)
                                if match:
                                    # we have a match
                                    found_intent = intent_type
                                    m, s = yield from hass.helpers.intent.async_handle(
                                        DOMAIN, intent_type,
                                        {key: {'value': value} for key, value
                                         in match.groupdict().items()},
                                        suffix + " " + text)
                                    # reset the curr button code
                                    CURR_BUTTON_CODE = 0
                                    break
        if s is False or found_intent is None:
            # no success - try to ask the cloud
            if m is None:
                # no message / no match
                m = 'Nie rozumiem ' + text
            # asking without the suffix
            ws_resp = aisCloudWS.ask(text, m)
            m = ws_resp.text

    except Exception as e:
        _LOGGER.warning('_process: ' + str(e))
        m = "Przepraszam, ale mam problem ze zrozumieniem: " + text
    # return response to the ais dom
    if m != 'DO_NOT_SAY':
        _say_it(hass, m, callback)
    # return response to the hass conversation
    intent_resp = intent.IntentResponse()
    intent_resp.async_set_speech(m)
    intent_resp.hass = hass
    return intent_resp


@core.callback
def _match_entity(hass, name):
    """Match a name to an entity."""
    from fuzzywuzzy import process as fuzzyExtract
    entities = {state.entity_id: state.name for state
                in hass.states.async_all()}
    try:
        entity_id = fuzzyExtract.extractOne(
            name, entities, score_cutoff=86)[2]
    except Exception as e:
        entity_id = None

    if entity_id is not None:
        return hass.states.get(entity_id)
    else:
        return None


class TurnOnIntent(intent.IntentHandler):
    """Handle turning item on intents."""

    intent_type = INTENT_TURN_ON
    slot_schema = {
        'item': cv.string,
    }

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle turn on intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots['item']['value']
        entity = _match_entity(hass, name)
        success = False

        if not entity:
            message = 'Nie znajduję urządzenia do włączenia, o nazwie: ' + name
        else:
            # check if we can turn_on on this device
            if isSwitch(entity.entity_id):
                assumed_state = entity.attributes.get(ATTR_ASSUMED_STATE, False)
                if assumed_state is False:
                    if entity.state == 'on':
                        # check if the device is already on
                        message = 'Urządzenie ' + name + ' jest już włączone'
                    elif entity.state == 'unavailable':
                        message = 'Urządzenie ' + name + ' jest niedostępne'
                    else:
                        assumed_state = True
                if assumed_state:
                    yield from hass.services.async_call(
                        core.DOMAIN, SERVICE_TURN_ON, {
                            ATTR_ENTITY_ID: entity.entity_id,
                        }, blocking=True)
                    message = 'OK, włączono {}'.format(entity.name)
                success = True
            else:
                message = 'Urządzenia ' + name + ' nie można włączyć'
        return message, success


class TurnOffIntent(intent.IntentHandler):
    """Handle turning item off intents."""

    intent_type = INTENT_TURN_OFF
    slot_schema = {
        'item': cv.string,
    }

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle turn off intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots['item']['value']
        entity = _match_entity(hass, name)
        success = False
        if not entity:
            msg = 'Nie znajduję urządzenia do wyłączenia, o nazwie: ' + name
        else:
            # check if we can turn_off on this device
            if isSwitch(entity.entity_id):
                assumed_state = entity.attributes.get(ATTR_ASSUMED_STATE, False)
                if assumed_state is False:
                    # check if the device is already off
                    if entity.state == 'off':
                        msg = 'Urządzenie {} jest już wyłączone'.format(
                            entity.name)
                    elif entity.state == 'unavailable':
                        msg = 'Urządzenie {}} jest niedostępne'.format(
                            entity.name)
                    else:
                        assumed_state = True
                if assumed_state:
                    yield from hass.services.async_call(
                        core.DOMAIN, SERVICE_TURN_OFF, {
                            ATTR_ENTITY_ID: entity.entity_id,
                        }, blocking=True)
                    msg = 'OK, wyłączono {}'.format(entity.name)
                    success = True
            else:
                msg = 'Urządzenia ' + name + ' nie można wyłączyć'
        return msg, success


class StatusIntent(intent.IntentHandler):
    """Handle status item on intents."""

    intent_type = INTENT_STATUS
    slot_schema = {
        'item': cv.string,
    }

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle status intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots['item']['value']
        entity = _match_entity(hass, name)
        success = False

        if not entity:
            message = 'Nie znajduję informacji o: ' + name
            success = False
        else:
            unit = entity.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            state = entity.state
            state = translate_state(state)
            if unit is None:
                value = state
            else:
                value = "{} {}".format(state, unit)
            message = format(entity.name) + ': ' + value
            success = True
        return message, success


class PlayRadioIntent(intent.IntentHandler):
    """Handle PlayRadio intents."""

    intent_type = INTENT_PLAY_RADIO
    slot_schema = {
        'item': cv.string
    }

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        item = slots['item']['value']
        station = item
        success = False
        if not station:
            message = 'Nie wiem jaką stację chcesz włączyć.'
        else:
            ws_resp = aisCloudWS.audio(
                station, ais_global.G_AN_RADIO, intent_obj.text_input)
            json_ws_resp = ws_resp.json()
            json_ws_resp["audio_type"] = ais_global.G_AN_RADIO
            name = json_ws_resp['name']
            if len(name.replace(" ", "")) == 0:
                message = "Niestety nie znajduję radia " + station
            else:
                yield from hass.services.async_call(
                     'ais_cloud', 'play_audio',
                     json_ws_resp, blocking=False)
                message = "OK, gramy radio " + name
                success = True
        return message, success


class AisPlayPodcastIntent(intent.IntentHandler):
    """Handle Podcast intents."""

    intent_type = INTENT_PLAY_PODCAST
    slot_schema = {
        'item': cv.string
    }

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        item = slots['item']['value']
        success = False

        if not item:
            message = 'Nie wiem jaką audycję chcesz posłuchać.'
        else:
            ws_resp = aisCloudWS.audio(
                item, ais_global.G_AN_PODCAST, intent_obj.text_input)
            json_ws_resp = ws_resp.json()
            json_ws_resp["audio_type"] = ais_global.G_AN_PODCAST
            name = json_ws_resp['name']
            if len(name.replace(" ", "")) == 0:
                message = "Niestety nie znajduję podcasta " + item
            else:
                yield from hass.services.async_call(
                     'ais_cloud', 'play_audio',
                     json_ws_resp, blocking=False)
                message = "OK, pobieram odcinki audycji " + item
                success = True
        return message, success


class AisPlayYtMusicIntent(intent.IntentHandler):
    """Handle Music intents."""

    intent_type = INTENT_PLAY_YT_MUSIC
    slot_schema = {
        'item': cv.string
    }

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        item = slots['item']['value']
        success = False

        if not item:
            message = 'Nie wiem jaką muzykę mam szukać '
        else:
            success = True
            yt_query = {}
            yt_query["audio_type"] = ais_global.G_AN_MUSIC
            yt_query["text"] = item
            yield from hass.services.async_call(
                 'ais_cloud', 'play_audio',
                 yt_query, blocking=False)
            message = "OK, szukam na YouTube " + item
            success = True
        return message, success


class AisPlaySpotifyIntent(intent.IntentHandler):
    """Handle Music intents."""

    intent_type = INTENT_PLAY_SPOTIFY
    slot_schema = {
        'item': cv.string
    }

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        item = slots['item']['value']
        success = False

        if not item:
            message = 'Nie wiem jaką muzykę mam szukać '
        else:
            _query = {"audio_type": ais_global.G_AN_SPOTIFY, "text": item}
            yield from hass.services.async_call(
                'ais_cloud', 'play_audio',
                _query, blocking=False)
            message = "OK, szukam na Spotify " + item
            success = True
        return message, success


class AskQuestionIntent(intent.IntentHandler):
    """Handle AskQuestion intents."""

    intent_type = INTENT_ASK_QUESTION
    slot_schema = {
        'item': cv.string
    }

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        item = slots['item']['value']
        question = item
        if not question:
            message = 'Nie wiem o co zapytać, ' + question
            return message, False
        else:
            yield from hass.services.async_call(
                 'ais_knowledge_service',
                 'ask', {"text": question, "say_it": True}, blocking=True)
        return 'DO_NOT_SAY', True


class ChangeContextIntent(intent.IntentHandler):
    """Handle ChangeContext intents."""
    intent_type = INTENT_CHANGE_CONTEXT

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        if len(GROUP_ENTITIES) == 0:
            get_groups(hass)
        text = intent_obj.text_input.lower()
        _LOGGER.debug('text: ' + text)
        for idx, menu in enumerate(GROUP_ENTITIES, start=0):
            context_key_words = menu['context_key_words']
            if context_key_words is not None:
                context_key_words = context_key_words.split(',')
                if text in context_key_words:
                    set_curr_group(hass, menu)
                    set_curr_entity(hass, None)
                    message = menu['context_answer']
                    # special case spotify and youtube
                    if text == 'spotify':
                        yield from hass.services.async_call(
                            'input_select', 'select_option',
                            {"entity_id": "input_select.ais_music_service", "option": "Spotify"})
                    elif text == 'youtube':
                        yield from hass.services.async_call(
                            'input_select', 'select_option',
                            {"entity_id": "input_select.ais_music_service", "option": "YouTube"})
                    return message, True

        message = 'Nie znajduję odpowiedzi do kontekstu ' + text
        return message, False


class GetTimeIntent(intent.IntentHandler):
    """Handle GetTimeIntent intents."""
    intent_type = INTENT_GET_TIME

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        # hass = intent_obj.hass
        # time = hass.states.get('sensor.time').state
        # message = 'Jest godzina ' + time
        import babel.dates
        now = datetime.datetime.now()
        message = 'Jest ' + babel.dates.format_time(
            now, format='short', locale='pl')
        return message, True


class AisGetWeather(intent.IntentHandler):
    """Handle GetWeather intents."""
    intent_type = INTENT_GET_WEATHER

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        # weather = hass.states.get('sensor.pogoda_info').state
        weather = "Pogoda "
        attr = hass.states.get('group.ais_pogoda').attributes
        for a in attr['entity_id']:
            w = hass.states.get(a)
            if a == 'sensor.dark_sky_hourly_summary':
                weather += " " + w.state + " "
            elif a == 'sensor.dark_sky_daily_summary':
                weather += " " + w.state + " "
            else:
                weather += w.attributes['friendly_name'] + " " + w.state + " "
                if 'unit_of_measurement' in w.attributes:
                    if w.attributes['unit_of_measurement'] == 'hPa':
                        weather += "hektopascala; "
                    elif w.attributes['unit_of_measurement'] == 'km/h':
                        weather += "kilometrów na godzinę; "
                    elif w.attributes['unit_of_measurement'] == 'km':
                        weather += "kilometra; "
                    else:
                        weather += w.attributes['unit_of_measurement'] + "; "
        return weather, True


class AisGetWeather48(intent.IntentHandler):
    """Handle GetWeather48 intents."""
    intent_type = INTENT_GET_WEATHER_48

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        weather = hass.states.get('sensor.dark_sky_daily_summary').state
        return weather, True


class AisLampsOn(intent.IntentHandler):
    """Handle AisLampsOn intents."""
    intent_type = INTENT_LAMPS_ON

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        yield from hass.services.async_call(
             'light', 'turn_on', {"entity_id": "group.all_lights"})
        return 'ok', True


class AisLampsOff(intent.IntentHandler):
    """Handle AisLampsOff intents."""
    intent_type = INTENT_LAMPS_OFF

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        yield from hass.services.async_call(
             'light', 'turn_off', {"entity_id": "group.all_lights"})
        return 'ok', True


class AisSwitchesOn(intent.IntentHandler):
    """Handle AisSwitchesOn intents."""
    intent_type = INTENT_SWITCHES_ON

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        yield from hass.services.async_call(
             'switch', 'turn_on', {"entity_id": "group.all_switches"})
        return 'ok', True


class AisSwitchesOff(intent.IntentHandler):
    """Handle AisSwitchesOff intents."""
    intent_type = INTENT_SWITCHES_OFF

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        yield from hass.services.async_call(
             'switch', 'turn_off', {"entity_id": "group.all_switches"})
        return 'ok', True


class GetDateIntent(intent.IntentHandler):
    """Handle GetDateIntent intents."""
    intent_type = INTENT_GET_DATE

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        import babel.dates
        now = datetime.datetime.now()
        message = 'Jest ' + babel.dates.format_date(
            now, format='full', locale='pl')
        return message, True


class AisOpenCover(intent.IntentHandler):
    """Handle AisOpenCover intents."""
    intent_type = INTENT_OPEN_COVER
    slot_schema = {
        'item': cv.string,
    }

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots['item']['value']
        entity = _match_entity(hass, name)
        success = False

        if not entity:
            message = 'Nie znajduję urządzenia do otwarcia, o nazwie: ' + name
        else:
            # check if we can open on this device
            if entity.entity_id.startswith('cover.'):
                if entity.state == 'on':
                    # check if the device is already on
                    message = 'Urządzenie ' + name + ' jest już otwarte'
                elif entity.state == 'unavailable':
                    message = 'Urządzenie ' + name + ' jest niedostępne'
                else:
                    yield from hass.services.async_call(
                        core.DOMAIN, SERVICE_OPEN_COVER, {
                            ATTR_ENTITY_ID: entity.entity_id,
                        }, blocking=True)
                    message = 'OK, włączono {}'.format(entity.name)
                success = True
            else:
                message = 'Urządzenia ' + name + ' nie można otworzyć'
        return message, success


class AisCloseCover(intent.IntentHandler):
    """Handle AisCloseCover intents."""
    intent_type = INTENT_CLOSE_COVER
    slot_schema = {
        'item': cv.string,
    }

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle turn off intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots['item']['value']
        entity = _match_entity(hass, name)
        success = False
        if not entity:
            msg = 'Nie znajduję urządzenia do zamknięcia, o nazwie: ' + name
        else:
            # check if we can close on this device
            if entity.entity_id.startswith('cover.'):
                # check if the device is already closed
                if entity.state == 'off':
                    msg = 'Urządzenie {} jest już zamknięte'.format(
                        entity.name)
                elif entity.state == 'unavailable':
                    msg = 'Urządzenie {} jest niedostępne'.format(
                        entity.name)
                else:
                    yield from hass.services.async_call(
                        core.DOMAIN, SERVICE_TURN_OFF, {
                            ATTR_ENTITY_ID: entity.entity_id,
                        }, blocking=True)
                    msg = 'OK, zamknięto {}'.format(entity.name)
                    success = True
            else:
                msg = 'Urządzenia ' + name + ' nie można zamknąć'
        return msg, success


class AisStop(intent.IntentHandler):
    """Handle AisStop intents."""
    intent_type = INTENT_STOP

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        yield from hass.services.async_call(
            'media_player', 'media_stop')
        message = 'ok, stop'
        return message, True


class AisPlay(intent.IntentHandler):
    """Handle AisPlay intents."""
    intent_type = INTENT_PLAY

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        yield from hass.services.async_call(
            'media_player', 'media_play', {
                ATTR_ENTITY_ID: "media_player.wbudowany_glosnik",
            })
        message = 'ok, gram'
        return message, True


class AisNext(intent.IntentHandler):
    """Handle AisNext intents."""
    intent_type = INTENT_NEXT

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        yield from hass.services.async_call(
            'media_player', 'media_next_track')
        message = 'ok, następny'
        return message, True


class AisPrev(intent.IntentHandler):
    """Handle AisPrev intents."""
    intent_type = INTENT_PREV

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        yield from hass.services.async_call(
            'media_player', 'media_previous_track')
        message = 'ok, poprzedni'
        return message, True


class AisSceneActive(intent.IntentHandler):
    """Handle AisSceneActive intents."""
    intent_type = INTENT_SCENE
    slot_schema = {
        'item': cv.string,
    }

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots['item']['value']
        entity = _match_entity(hass, name)
        success = False

        if not entity:
            message = 'Nie znajduję sceny, o nazwie: ' + name
        else:
            # check if we can open on this device
            if entity.entity_id.startswith('scene.'):
                yield from hass.services.async_call(
                    'scene', 'turn_on', {
                        ATTR_ENTITY_ID: entity.entity_id,
                    }, blocking=True)
                message = 'OK, aktywuję {}'.format(entity.name)
                success = True
            else:
                message = name + ' nie można aktywować'
        return message, success


class AisSayIt(intent.IntentHandler):
    """Handle AisSayIt intents."""
    intent_type = INTENT_SAY_IT
    slot_schema = {
        'item': cv.string,
    }

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        try:
            slots = self.async_validate_slots(intent_obj.slots)
            text = slots['item']['value']
        except Exception:
            text = None
        success = False
        if not text:
            import random
            answers = ['Nie wiem co mam powiedzieć?', 'Ale co?', 'Mówie mówie', 'OK, dobra zaraz coś wymyślę...',
                       'Mowa jest tylko srebrem', 'To samo czy coś nowego?']
            message = random.choice(answers)
        else:
            # check if we can open on this device
            message = text
            success = True
        return message, success


class AisClimateSetTemperature(intent.IntentHandler):
    """Handle AisClimateSetTemperature intents."""
    intent_type = INTENT_CLIMATE_SET_TEMPERATURE
    slot_schema = {
        'temp': cv.positive_int,
        'item': cv.string,
    }

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        try:
            hass = intent_obj.hass
            slots = self.async_validate_slots(intent_obj.slots)
            temp = slots['temp']['value']
            name = slots['item']['value']
            entity = _match_entity(hass, name)
        except Exception:
            text = None
        success = False
        if not entity:
            msg = 'Nie znajduję grzejnika, o nazwie: ' + name
        else:
            # check if we can close on this device
            if entity.entity_id.startswith('climate.'):
                # check if the device has already this temperature
                attr = hass.states.get(entity.entity_id).attributes
                if attr.get('temperature') == temp:
                    msg = '{} ma już ustawioną temperaturę {}'.format(
                        entity.name, temp)
                else:
                    yield from hass.services.async_call(
                        'climate', 'set_temperature', {
                            ATTR_ENTITY_ID: entity.entity_id,
                            "temperature": temp,
                            "target_temp_high": temp + 2,
                            "target_temp_low": temp - 6,
                            "operation_mode": "Heat"
                        }, blocking=True)
                    msg = 'OK, ustawiono temperaturę {} w {}'.format(temp, entity.name)
                    success = True
            else:
                msg = 'Na urządzeniu ' + name + ' nie można zmieniać temperatury.'
        return msg, success


class AisClimateSetAway(intent.IntentHandler):
    """Handle AisClimateSetAway intents."""
    intent_type = INTENT_CLIMATE_SET_AWAY

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        yield from hass.services.async_call(
            'climate', 'set_away_mode', {"entity_id": "all", "away_mode": True})
        message = 'ok, tryb poza domem włączony'
        return message, True


class AisClimateUnSetAway(intent.IntentHandler):
    """Handle AisClimateUnSetAway intents."""
    intent_type = INTENT_CLIMATE_UNSET_AWAY

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        yield from hass.services.async_call(
            'climate', 'set_away_mode', {"entity_id": "all", "away_mode": False})
        message = 'ok, tryb poza domem wyłączony'
        return message, True


class AisClimateSetAllOn(intent.IntentHandler):
    """Handle AisClimateSetAllOn intents."""
    intent_type = INTENT_CLIMATE_SET_ALL_ON

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        yield from hass.services.async_call(
            'climate', 'set_operation_mode', {"entity_id": "all", 'operation_mode': 'heat'})
        message = 'ok, całe ogrzewanie włączone'
        return message, True


class AisClimateSetAllOff(intent.IntentHandler):
    """Handle AisClimateSetAllOff intents."""
    intent_type = INTENT_CLIMATE_SET_ALL_OFF

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        yield from hass.services.async_call(
            'climate', 'set_operation_mode', {"entity_id": "all", 'operation_mode': 'off'})
        message = 'ok, całe ogrzewanie wyłączone'
        return message, True

# class AisClimateSetOff(intent.IntentHandler):
#     """Handle AisClimateSetOff intents."""
#     intent_type = INTENT_CLIMATE_SET_OFF
#     slot_schema = {
#         'item': cv.string,
#     }
#
#     @asyncio.coroutine
#     def async_handle(self, intent_obj):
#         """Handle the intent."""
#         try:
#             hass = intent_obj.hass
#             slots = self.async_validate_slots(intent_obj.slots)
#             name = slots['item']['value']
#             entity = _match_entity(hass, name)
#         except Exception:
#             text = None
#         success = False
#         if not entity:
#             msg = 'Nie znajduję grzejnika, o nazwie: ' + name
#         else:
#             # check if we can close on this device
#             if entity.entity_id.startswith('climate.'):
#             # check if the device already is off
#                 if entity.state == 'off':
#                     msg = '{} jest już wyłączony'.format(entity.name)
#                 elif entity.state == 'unavailable':
#                     msg = '{} jest niedostępny'.format(entity.name)
#                 else:
#                     yield from hass.services.async_call(
#                         'climate', 'turn_off', {
#                             ATTR_ENTITY_ID: entity.entity_id
#                         }, blocking=True)
#                     msg = 'OK, wyłączono ogrzewanie {} '.format(entity.name)
#                     success = True
#             else:
#                 msg = 'Na urządzeniu ' + name + ' nie można wyłączyć ogrzwania.'
#             return msg, success
#
#
# class AisClimateSetOn(intent.IntentHandler):
#     """Handle AisClimateSetOn intents."""
#     intent_type = INTENT_CLIMATE_SET_ON
#     slot_schema = {
#         'item': cv.string,
#     }
#
#     @asyncio.coroutine
#     def async_handle(self, intent_obj):
#         """Handle the intent."""
#         try:
#             hass = intent_obj.hass
#             slots = self.async_validate_slots(intent_obj.slots)
#             name = slots['item']['value']
#             entity = _match_entity(hass, name)
#         except Exception:
#             text = None
#         success = False
#         if not entity:
#             msg = 'Nie znajduję grzejnika, o nazwie: ' + name
#         else:
#             # check if we can close on this device
#             if entity.entity_id.startswith('climate.'):
#                 # check if the device already is heat
#                 if entity.state == 'heat':
#                     msg = '{} jest już włączony'.format(entity.name)
#                 elif entity.state == 'unavailable':
#                     msg = '{} jest niedostępny'.format(entity.name)
#                 else:
#                     yield from hass.services.async_call(
#                         'climate', 'turn_on', {
#                             ATTR_ENTITY_ID: entity.entity_id
#                         }, blocking=True)
#                     msg = 'OK, wyłączono ogrzewanie {} '.format(entity.name)
#                     success = True
#             else:
#                 msg = 'Na urządzeniu ' + name + ' nie można wyłączyć ogrzwania.'
#             return msg, success
