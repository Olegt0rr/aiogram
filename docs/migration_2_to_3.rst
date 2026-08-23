.. |Bot| replace:: :class:`~aiogram.client.bot.Bot`
.. |Dispatcher| replace:: :class:`~aiogram.dispatcher.dispatcher.Dispatcher`
.. |Router| replace:: :class:`~aiogram.dispatcher.router.Router`

==========================
Migration FAQ (2.x -> 3.0)
==========================

This version introduces numerous breaking changes and architectural improvements.
It helps reduce the count of global variables in your code, provides useful mechanisms
to modularize your code, and enables the creation of shareable modules via packages on PyPI.
It also makes middlewares and filters more controllable, among other improvements.

On this page, you can read about the changes made in relation to the last stable 2.x version.

.. note::

    Feel free to contribute to this page, if you find something that is not mentioned here.

.. danger::

    Most breaking changes on this page fall into two groups:
    code that **fails loudly** right after the upgrade (import errors, removed methods)
    and code that **fails silently** — it imports and runs, but misbehaves only on
    specific updates or under specific conditions.
    The silent group is marked with warnings across this page; pay extra attention to it.


Dependencies
============

- The dependencies required for :code:`i18n` are no longer part of the default package.
  If your application uses translation functionality, be sure to add an optional dependency:

  :code:`pip install aiogram[i18n]`

  Note that the i18n API itself has also been changed, see :ref:`i18n migration <migration-i18n>` below.

- aiogram 3.x requires :code:`aiohttp >= 3.9` (v2 worked with older versions).
  If your project uses aiohttp directly (for example, for a webhook web application),
  check your own code against the aiohttp changelog: arguments that were deprecated
  in older aiohttp versions have been removed (e.g. the :code:`loop=` argument of
  :code:`aiohttp.web.Application`).

- Redis storage is now based on the `redis <https://pypi.org/project/redis/>`_ package
  (with asyncio support) instead of :code:`aioredis`.


Bot
===

Default bot properties (parse_mode and others)
----------------------------------------------

In v2 the global parse mode was configured directly on the |Bot| instance
(:code:`Bot(token, parse_mode="HTML")`). In v3 all per-bot defaults are grouped into
:class:`~aiogram.client.default.DefaultBotProperties`:

.. code-block:: python

    # Version 2.x
    bot = Bot(token, parse_mode="HTML")

.. code-block:: python

    # Version 3.x
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode

    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

:class:`~aiogram.client.default.DefaultBotProperties` also covers other defaults:
:code:`disable_notification`, :code:`protect_content`, :code:`link_preview_is_disabled`
and other link preview options, etc.

.. note::

    In aiogram 3.0 - 3.6 the :code:`Bot(parse_mode=...)` form was still accepted;
    it was removed in 3.7 in favor of :code:`DefaultBotProperties`.
    If you migrate straight to a recent 3.x release, use :code:`DefaultBotProperties` only.

:code:`bot.me` is now a method
------------------------------

In v2 :code:`me` was a property (:code:`me = await bot.me`), in v3 it is a method
(with cached result):

.. code-block:: python

    # Version 2.x
    me = await bot.me

    # Version 3.x
    me = await bot.me()

.. warning::

    This is a silent breakage: :code:`await bot.me` in v3 fails only at runtime
    (awaiting a method object), so grep your project for :code:`.me` usages.

Bot is no longer a context storage
----------------------------------

In v2 both |Bot| and |Dispatcher| could be used as dictionaries to store arbitrary
runtime data (:code:`bot["db"] = ...`, documented as a feature). In v3:

- |Dispatcher| still supports this via
  :code:`dispatcher.workflow_data` (:code:`dp["key"] = value` still works),
  and all values stored there are automatically injected into handlers,
  filters, and middlewares as keyword arguments by name.
- |Bot| is no longer a data storage of any kind.

.. code-block:: python

    # Version 2.x
    bot["db"] = db
    dp["config"] = config

    # Version 3.x
    dp["db"] = db          # or Dispatcher(db=db, config=config)
    dp["config"] = config

    @router.message(Command("info"))
    async def handler(message: Message, db: Database, config: Config) -> None:
        # values from workflow_data are injected by argument name
        ...

If you stored data on the |Bot| instance because multiple bots shared one dispatcher,
move that data to a middleware or derive it from the :code:`bot` argument
(e.g. keyed by :code:`bot.id`).

Downloading files
-----------------

The v2 method :code:`bot.download_file_by_id` was removed;
use :meth:`~aiogram.client.bot.Bot.download` which accepts
both a file id and a :class:`~aiogram.types.file.File`-like object.


Dispatcher
==========

- The |Dispatcher| class no longer accepts a |Bot| instance in its initializer.
  Instead, the |Bot| instance should be passed to the dispatcher only for starting polling
  or handling events from webhooks. This approach also allows for the use of multiple bot
  instances simultaneously ("multibot").
- |Dispatcher| now can be extended with another Dispatcher-like thing named |Router|.
  With routes, you can easily modularize your code and potentially share these modules between projects.
  (:ref:`Read more » <Nested routers>`.)
- Removed the **_handler** suffix from all event handler decorators and registering methods.
  (:ref:`Read more » <Event observers>`)
- The :class:`Executor` has been entirely removed; you can now use the |Dispatcher| directly to start poll the API or handle webhooks from it.
- Throttling (:code:`dp.throttle`, :code:`Throttled`, the :code:`rate_limit` pattern) has been
  completely removed; see the :ref:`Throttling <migration-throttling>` section for the
  replacement recipe based on middlewares and flags.
- Removed global context variables from the API types, |Bot| and |Dispatcher| object.
  From now on, if you want to access the current bot instance within handlers or filters,
  you should accept the argument :code:`bot: Bot` and use it instead of :code:`Bot.get_current()`.
  In middlewares, it can be accessed via :code:`data["bot"]`.
- To skip pending updates, you should now call the :class:`~aiogram.methods.delete_webhook.DeleteWebhook` method directly, rather than passing :code:`skip_updates=True` to the start polling method.
- To feed updates to the |Dispatcher|, instead of method :meth:`process_update`,
  you should use method :meth:`~aiogram.dispatcher.dispatcher.Dispatcher.feed_update`.
  (:ref:`Read more » <Handling updates>`)

Background handler execution (:code:`run_task`) is removed
----------------------------------------------------------

The v2 options :code:`Dispatcher(run_tasks_by_default=True)` and
:code:`@dp.message_handler(run_task=True)`, which executed handlers in background tasks,
were removed without a direct equivalent.

In v3, each **update** is already processed in its own task during polling
(:code:`start_polling(handle_as_tasks=True)` is the default), so slow handlers do not
block other users. If you still need fire-and-forget behavior inside a handler,
schedule the work explicitly:

.. code-block:: python

    @router.message(Command("slow"))
    async def handler(message: Message) -> None:
        asyncio.create_task(do_slow_work(message.chat.id))
        # keep a reference to the task if it must not be garbage-collected

:code:`AllowedUpdates` helper is removed
----------------------------------------

The v2 helper :code:`aiogram.types.AllowedUpdates` no longer exists.
In v3 pass plain strings or :class:`aiogram.enums.UpdateType` members,
or resolve the list from your registered handlers via
:meth:`~aiogram.dispatcher.router.Router.resolve_used_update_types`:

.. code-block:: python

    # Version 2.x
    executor.start_polling(dp, allowed_updates=types.AllowedUpdates.MESSAGE)

.. code-block:: python

    # Version 3.x
    from aiogram.enums import UpdateType

    await dp.start_polling(bot, allowed_updates=[UpdateType.MESSAGE])
    # or let aiogram compute it from your handlers:
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

.. warning::

    When :code:`allowed_updates` is not passed to :code:`start_polling`, aiogram 3
    automatically requests **only the update types for which you have handlers**
    (it calls :code:`resolve_used_update_types()` for you). This differs from v2,
    where the bot received the server-default set of updates. If some of your updates
    are consumed only by middlewares or outside the dispatcher, pass
    :code:`allowed_updates` explicitly.


Filtering events
================

- Keyword filters can no longer be used; use filters explicitly. (`Read more » <https://github.com/aiogram/aiogram/issues/942>`_)
- Due to the removal of keyword filters, all previously enabled-by-default filters
  (such as state and content_type) are now disabled.
  You must specify them explicitly if you wish to use them.
  For example instead of using :code:`@dp.message_handler(content_types=ContentType.PHOTO)`
  you should use :code:`@router.message(F.photo)`
- Most common filters have been replaced with the "magic filter." (:ref:`Read more » <magic-filters>`)
- By default, the message handler now receives any content type.
  If you want a specific one, simply add the appropriate filters (Magic or any other).
- Added the possibility to register global filters for each router, which helps to reduce code
  repetition and provides an easier way to control the purpose of each router.

The :code:`chat_type` filter
----------------------------

The commonly used v2 keyword filter :code:`chat_type=` should be replaced with a magic
filter. Note that **the path to the chat differs between event types**:

.. code-block:: python

    # Version 2.x
    @dp.message_handler(chat_type=types.ChatType.PRIVATE)
    @dp.callback_query_handler(chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])

.. code-block:: python

    # Version 3.x
    from aiogram import F
    from aiogram.enums import ChatType

    @router.message(F.chat.type == ChatType.PRIVATE)
    @router.callback_query(F.message.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))

For a message the chat is :code:`F.chat`, but for a callback query the chat lives on the
attached message: :code:`F.message.chat`. A copied-over :code:`F.chat.type` filter on a
callback query handler will simply never match.

The :code:`Text` filter
-----------------------

The v2 :code:`Text` filter has no equivalent in current 3.x releases
(it existed in early 3.x versions and was removed in 3.4). Use the magic filter:

.. code-block:: python

    # Version 2.x
    @dp.message_handler(text="hello")
    @dp.message_handler(text_startswith="foo")

.. code-block:: python

    # Version 3.x
    @router.message(F.text == "hello")
    @router.message(F.text.startswith("foo"))
    # also useful: F.text.in_({...}), F.text.contains(...),
    # case-insensitive: F.text.casefold() == "hello"

.. note::

    Don't confuse the removed filter with :class:`aiogram.utils.formatting.Text` —
    that one is a text formatting tool, not a filter.

Command arguments (:code:`message.get_args`)
--------------------------------------------

The v2 method :code:`Message.get_args()` is removed. The :class:`~aiogram.filters.command.Command`
filter now passes a :class:`~aiogram.filters.command.CommandObject` into the handler:

.. code-block:: python

    # Version 2.x
    @dp.message_handler(commands=["start"])
    async def handler(message: types.Message):
        args = message.get_args()  # "" if no args

.. code-block:: python

    # Version 3.x
    from aiogram.filters import Command, CommandObject

    @router.message(Command("start"))
    async def handler(message: Message, command: CommandObject) -> None:
        args = command.args  # None if no args

Note that :code:`command.args` is :code:`None` (not an empty string) when the command
has no arguments.

Default state filter behavior is inverted
-----------------------------------------

.. warning::

    This is one of the most dangerous silent changes in v3.

    - In v2 a handler **without** a state filter ran only in the default (no) state;
      to run in any state you had to pass :code:`state="*"`.
    - In v3 a handler **without** a :class:`~aiogram.filters.state.StateFilter` runs in **any** state.

    After a naive migration, handlers start to trigger in situations where they were
    silently skipped before — e.g. a menu handler now fires in the middle of an FSM dialog.

    Migration rules:

    - v2 :code:`state="*"` -> v3: no state filter at all.
    - v2 without state -> v3: :code:`StateFilter(None)` if you want to keep the old behavior.
    - v2 :code:`state=MyGroup.my_state` -> v3: :code:`StateFilter(MyGroup.my_state)`
      (or pass the state directly as a filter: :code:`@router.message(MyGroup.my_state)`).


Bot API
=======

- All API methods are now classes with validation, implemented via
  `pydantic <https://docs.pydantic.dev/>`_.
  These API calls are also available as methods in the Bot class.
- More pre-defined Enums have been added and moved to the `aiogram.enums` sub-package.
  For example, the chat type enum is now :class:`aiogram.enums.ChatType` instead of :class:`aiogram.types.chat.ChatType`.
- The HTTP client session has been separated into a container that can be reused
  across different Bot instances within the application.
- API Exceptions are no longer classified by specific messages,
  as Telegram has no documented error codes.
  However, all errors are classified by HTTP status codes, and for each method,
  only one type of error can be associated with a given code.
  Therefore, in most cases, you should check only the error type (by status code)
  without inspecting the error message. More details can be found in the
  :ref:`exceptions section » <error-types>`.

Renamed methods
---------------

v2 kept some pre-Bot API 5.3 method names that are gone in v3:

- :code:`kick_chat_member` -> :meth:`~aiogram.client.bot.Bot.ban_chat_member`
- :code:`get_chat_members_count` -> :meth:`~aiogram.client.bot.Bot.get_chat_member_count`
- :code:`set_sticker_set_thumb` -> :meth:`~aiogram.client.bot.Bot.set_sticker_set_thumbnail`
- :code:`close_bot` -> :meth:`~aiogram.client.bot.Bot.close` (the Bot API :code:`close` method;
  to close the HTTP client session, use :code:`await bot.session.close()`)
- :code:`download_file_by_id` -> :meth:`~aiogram.client.bot.Bot.download`

All other methods follow the current Bot API names — when in doubt, check the method
list in the API reference rather than assuming the v2 name still exists.

Constructors of types and methods are keyword-only
--------------------------------------------------

All Telegram types and API methods are `pydantic <https://docs.pydantic.dev/>`_ models
now, so positional arguments are not accepted:

.. code-block:: python

    # Version 2.x
    button = InlineKeyboardButton("Press me", callback_data="click")
    command = BotCommand("help", "Show help")

.. code-block:: python

    # Version 3.x
    button = InlineKeyboardButton(text="Press me", callback_data="click")
    command = BotCommand(command="help", description="Show help")

Positional construction fails with a validation error at runtime, so this cannot be
caught by import checks — grep for positional usages of Telegram types while migrating.


Telegram objects behavior
=========================

Objects are immutable (frozen)
------------------------------

All Telegram types in v3 are immutable pydantic models. Any code that mutated objects
in-place (most commonly tests) must be updated:

.. code-block:: python

    # Version 2.x
    message.text = "edited"

.. code-block:: python

    # Version 3.x
    new_message = message.model_copy(update={"text": "edited"})

Optional list fields are :code:`None`, not :code:`[]`
-----------------------------------------------------

.. warning::

    In v2, fields like :code:`message.entities`, :code:`message.photo`,
    :code:`message.caption_entities`, :code:`message.new_chat_members` defaulted to
    empty lists. In v3 they are :code:`None` when absent, matching the Bot API.
    Code like :code:`for entity in message.entities:` passes review and works on
    most messages, then raises :code:`TypeError` on the first message without
    entities. Use:

    .. code-block:: python

        for entity in message.entities or []:
            ...

The :code:`.bot` attribute and shortcut methods
-----------------------------------------------

In v2 shortcuts like :code:`message.answer(...)` resolved the bot instance from a global
context. In v3 the bot instance is attached to every object **during deserialization of
an update**, through the pydantic validation context.

Consequences:

- Objects received in handlers work as before: :code:`await message.answer(...)` is fine.
- Objects you create manually (or deserialize yourself) have :code:`bot=None`,
  and their shortcut methods will fail. Bind the bot explicitly:

  .. code-block:: python

      message = Message.model_validate(data, context={"bot": bot})
      # or for an existing object:
      message = message.as_(bot)

- For background tasks and code far from handlers, pass the :code:`bot` instance
  explicitly instead of relying on shortcuts of stored objects.

Forwarded messages: :code:`forward_from` is dead
------------------------------------------------

.. warning::

    The v2-era fields :code:`forward_from`, :code:`forward_from_chat`,
    :code:`forward_from_message_id` still exist on :class:`~aiogram.types.message.Message`
    (deprecated), but since Bot API 7.0 Telegram **no longer sends them** — so migrated
    code that reads them compiles and silently sees :code:`None`.
    Use :attr:`~aiogram.types.message.Message.forward_origin` instead:

    .. code-block:: python

        from aiogram.types import MessageOriginUser

        if isinstance(message.forward_origin, MessageOriginUser):
            original_sender = message.forward_origin.sender_user


Exceptions
==========

Mapping (v2 -> v3)
-------------------

- RetryAfter -> :class:`TelegramRetryAfter` (:mod:`aiogram.exceptions`)
  - Important attribute in v3: ``retry_after`` (int).

- ChatMigrated / MigrateToChat -> :class:`TelegramMigrateToChat`
  - Important attribute in v3: ``migrate_to_chat_id`` (int).

- ClientDecodeError -> :class:`ClientDecodeError`
  - Important attributes in v3: ``original`` (Exception) and ``data`` (response body).

- BadRequest -> :class:`TelegramBadRequest`
- Unauthorized -> :class:`TelegramUnauthorizedError`
- Forbidden -> :class:`TelegramForbiddenError`
- NotFound -> :class:`TelegramNotFound`
- Conflict -> :class:`TelegramConflictError`
- ServerError -> :class:`TelegramServerError`
- NetworkError -> :class:`TelegramNetworkError`
- EntityTooLarge -> :class:`TelegramEntityTooLarge`

.. warning::

    Attributes were renamed too, not only the classes. The most important one:
    v2 :code:`RetryAfter.timeout` is now :code:`TelegramRetryAfter.retry_after`.
    An :code:`except` block migrated only by class name compiles fine and crashes
    with :code:`AttributeError` **only under flood limits**:

    .. code-block:: python

        # Version 2.x
        except exceptions.RetryAfter as e:
            await asyncio.sleep(e.timeout)

    .. code-block:: python

        # Version 3.x
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)

    (:code:`migrate_to_chat_id` kept its name from v2 :code:`MigrateToChat`.)

Exceptions removed in v3 (from v2)
----------------------------------

The list below contains common exception names that appeared in aiogram v2 but
are not defined as separate classes in the v3 codebase. For each v2 name, a
recommended v3 replacement (or handling) is provided — keep your migration
logic simple and rely on the v3 exception classes and their attributes.

- MessageNotModified -> :class:`TelegramBadRequest`
- MessageToEditNotFound -> :class:`TelegramNotFound`
- MessageToDeleteNotFound -> :class:`TelegramNotFound`
- MessageCantBeDeleted -> :class:`TelegramForbiddenError` / :class:`TelegramBadRequest`
- CantParseEntities -> :class:`TelegramBadRequest`
- MessageIsTooLong -> :class:`TelegramEntityTooLarge`
- MessageIdentifierNotFound -> :class:`TelegramNotFound`
- UserDeactivated -> :class:`TelegramForbiddenError`
- CantInitiateConversation -> :class:`TelegramBadRequest`
- StickerSetNameInvalid -> :class:`TelegramBadRequest`
- ChatAdminRequired -> :class:`TelegramForbiddenError`

Use these replacements when migrating exception handling from v2 to v3. If
you relied on catching very specific v2 exception classes, replace those
handlers with the corresponding v3 class above (or catch a broader v3 class
such as :class:`TelegramBadRequest` / :class:`TelegramAPIError`) and inspect
available attributes (see "Mapping (v2 -> v3)") for any required details.


Error handlers
==============

The signature and registration of error handlers changed completely:

.. code-block:: python

    # Version 2.x
    @dp.errors_handler(exception=MyCustomError)
    async def my_error_handler(update: types.Update, exception: Exception):
        ...
        return True  # mark error as handled, stop propagation

.. code-block:: python

    # Version 3.x
    from aiogram.filters import ExceptionTypeFilter
    from aiogram.types import ErrorEvent

    @router.error(ExceptionTypeFilter(MyCustomError), F.update.message.as_("message"))
    async def my_error_handler(event: ErrorEvent, message: Message) -> None:
        await message.answer("Oops, something went wrong!")

Key differences:

- The handler receives a single :class:`~aiogram.types.error_event.ErrorEvent`
  with :code:`event.update` and :code:`event.exception`, instead of two arguments.
- Filtering by exception type is done with
  :class:`~aiogram.filters.exception.ExceptionTypeFilter` instead of the
  :code:`exception=` keyword.
- v2 semantics "return :code:`True` to stop other error handlers" is gone.
  Error handlers now behave like any other observer: the first handler whose
  filters match handles the error, and propagation stops — no return value is needed.
- Errors unhandled by any error handler are logged by the :code:`aiogram.event` logger.

Read more: :ref:`Error handling docs <error-event>`.


Middlewares
===========

- Middlewares can now control an execution context, e.g., using context managers.
  (:ref:`Read more » <middlewares>`)
- All contextual data is now shared end-to-end between middlewares, filters, and handlers.
  For example now you can easily pass some data into context inside middleware and
  get it in the filters layer as the same way as in the handlers via keyword arguments.
- Added a mechanism named **flags** that helps customize handler behavior
  in conjunction with middlewares. (:ref:`Read more » <flags>`)
- :code:`aiogram.contrib.middlewares.logging.LoggingMiddleware` is removed together with
  the whole :code:`aiogram.contrib` package. Use standard :mod:`logging` configuration
  for aiogram loggers (:code:`aiogram.event` and others), or write a trivial middleware.

.. _migration-throttling:

Throttling
==========

The entire v2 throttling API was removed **with no built-in replacement**:

- :code:`dp.throttle()`, :code:`dp.check_key()`, :code:`dp.release_key()`
- the :code:`Throttled` exception
- the :code:`rate_limit` decorator and the :code:`ThrottlingMiddleware` recipe
  from the official v2 documentation
- :code:`CancelHandler` / :code:`current_handler` used by that recipe
  (in v3 a middleware simply returns without calling :code:`handler(...)`
  to drop an event)
- the "bucket" API of FSM storages (:code:`get_bucket` / :code:`set_bucket`) —
  v3 storages keep only state and data

The v3 approach is a middleware, optionally configured per-handler with
:ref:`flags <flags>`:

.. code-block:: python

    from collections.abc import Awaitable, Callable
    from time import monotonic
    from typing import Any

    from aiogram import BaseMiddleware
    from aiogram.dispatcher.flags import get_flag
    from aiogram.types import Message


    class ThrottlingMiddleware(BaseMiddleware):
        def __init__(self, default_rate: float = 0.5) -> None:
            self.default_rate = default_rate
            self.last_call: dict[int, float] = {}

        async def __call__(
            self,
            handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
            event: Message,
            data: dict[str, Any],
        ) -> Any:
            rate = self.default_rate
            flag = get_flag(data, "rate_limit")
            if flag is not None:
                rate = flag.get("rate", self.default_rate)

            key = event.from_user.id
            now = monotonic()
            last = self.last_call.get(key)
            if last is not None and now - last < rate:
                return None  # drop the event
            self.last_call[key] = now
            return await handler(event, data)

.. code-block:: python

    from aiogram import flags

    router.message.middleware(ThrottlingMiddleware())


    @router.message(Command("expensive"))
    @flags.rate_limit(rate=5.0)
    async def handler(message: Message) -> None:
        ...

.. note::

    The example above keeps timestamps in an unbounded in-memory dict to stay short.
    In production, use a TTL cache or your storage backend, and answer the user
    ("too many requests") instead of dropping silently if that fits your UX.


Keyboard Markup
===============

- Now :class:`aiogram.types.inline_keyboard_markup.InlineKeyboardMarkup`
  and :class:`aiogram.types.reply_keyboard_markup.ReplyKeyboardMarkup` no longer have methods for extension,
  instead you have to use markup builders :class:`aiogram.utils.keyboard.ReplyKeyboardBuilder`
  and :class:`aiogram.utils.keyboard.KeyboardBuilder` respectively
  (:ref:`Read more » <Keyboard builder>`)
- Buttons are constructed with keyword-only arguments now, see
  `Constructors of types and methods are keyword-only`_.


Callbacks data
==============

- The callback data factory is now strictly typed using `pydantic <https://docs.pydantic.dev/>`_ models.
  (:ref:`Read more » <Callback data factory>`)


Finite State machine
====================

- State filters will no longer be automatically added to all handlers;
  you will need to specify the state if you want to use it.
  Pay attention to the inverted default described in
  `Default state filter behavior is inverted`_.
- Added the possibility to change the FSM strategy. For example,
  if you want to control the state for each user based on chat topics rather than
  the user in a chat, you can specify this in the |Dispatcher|.
- Now :class:`aiogram.fsm.state.State` and :class:`aiogram.fsm.state.StateGroup` don't have helper
  methods like :code:`.set()`, :code:`.next()`, etc.
  Instead, you should set states by passing them directly to
  :class:`aiogram.fsm.context.FSMContext` (:ref:`Read more » <Finite State Machine>`)
- The state proxy is deprecated; you should update the state data by calling
  :code:`state.set_data(...)` and :code:`state.get_data()` respectively.
- Storages moved from :code:`aiogram.contrib.fsm_storage` to :code:`aiogram.fsm.storage`:

  - :code:`aiogram.contrib.fsm_storage.memory.MemoryStorage` -> :class:`aiogram.fsm.storage.memory.MemoryStorage`
  - :code:`aiogram.contrib.fsm_storage.redis.RedisStorage2` -> :class:`aiogram.fsm.storage.redis.RedisStorage`
  - :code:`aiogram.contrib.fsm_storage.mongo.MongoStorage` -> :class:`aiogram.fsm.storage.mongo.MongoStorage`

Storage keys and migrating live states (Redis)
----------------------------------------------

.. warning::

    If the key format of your v3 storage does not match the keys your v2 bot wrote,
    all live user states are silently "lost" after the deploy: the bot simply reads
    empty state for everyone. Verify key compatibility **before** switching over.

In v3 the storage key layout is controlled by a
:class:`~aiogram.fsm.storage.base.KeyBuilder`. The default
:class:`~aiogram.fsm.storage.base.DefaultKeyBuilder` produces::

    fsm:<chat_id>:<user_id>:state
    fsm:<chat_id>:<user_id>:data

This happens to match the **default** v2 :code:`RedisStorage2` layout
(:code:`fsm:<chat>:<user>:state`). But if your v2 setup used a custom
:code:`prefix`, or the older v2 :code:`RedisStorage` (v1-style), the formats differ.
Many v2 layouts can be reproduced by configuring the builder:

.. code-block:: python

    from aiogram.fsm.storage.base import DefaultKeyBuilder
    from aiogram.fsm.storage.redis import RedisStorage

    storage = RedisStorage.from_url(
        "redis://localhost:6379/0",
        key_builder=DefaultKeyBuilder(
            prefix="my_fsm_key",  # your v2 prefix, default "fsm"
            with_bot_id=False,    # v2 keys never contained bot id
        ),
    )

Notes:

- :code:`with_bot_id=True` is recommended for **new** projects and required for
  multibot setups, but it changes the key format — don't enable it while you still
  need to read v2-era keys.
- If your v2 format can't be reproduced (e.g. the old hash-based v2 :code:`RedisStorage`),
  implement a custom :class:`~aiogram.fsm.storage.base.KeyBuilder` or migrate the data
  with a one-off script.
- Keys of the third v2 record type — :code:`...:bucket` — belonged to the removed
  throttling API; v3 never reads them, so they can be deleted.
- Check with :code:`redis-cli --scan --pattern 'fsm:*'` (or your prefix) that the v3 bot
  reads and writes exactly the same keys as the v2 bot did.


Sending Files
=============

In v2 you could pass an IO object directly to the API method or wrap it in the
:code:`InputFile` class. In v3, :class:`~aiogram.types.input_file.InputFile` is
**abstract** and cannot be instantiated or receive raw IO objects — use one of the
concrete classes:

- :class:`~aiogram.types.input_file.FSInputFile` — file on the local filesystem
- :class:`~aiogram.types.input_file.BufferedInputFile` — :code:`bytes` in memory
- :class:`~aiogram.types.input_file.URLInputFile` — file by URL

.. code-block:: python

    # Version 2.x
    await bot.send_photo(chat_id, photo=open("photo.png", "rb"))
    # or
    await bot.send_photo(chat_id, photo=types.InputFile("photo.png"))

.. code-block:: python

    # Version 3.x
    from aiogram.types import FSInputFile

    await bot.send_photo(chat_id, photo=FSInputFile("photo.png"))

(:ref:`Read more » <sending-files>`)


Utilities and contrib
=====================

The whole :code:`aiogram.contrib` package is removed. Where its contents went:

- :code:`aiogram.contrib.fsm_storage.*` -> :code:`aiogram.fsm.storage.*`
  (see `Finite State machine`_)
- :code:`aiogram.contrib.middlewares.logging.LoggingMiddleware` -> removed,
  use standard :mod:`logging` (see `Middlewares`_)
- :code:`aiogram.contrib.middlewares.i18n.I18nMiddleware` -> :code:`aiogram.utils.i18n`
  (see :ref:`below <migration-i18n>`)

Other utility changes:

- :code:`aiogram.utils.json` (JSON library selection) is removed without replacement;
  aiogram handles serialization internally.
- :code:`aiogram.utils.mixins` is **not** removed — contrary to a widespread belief:
  :class:`~aiogram.utils.mixins.ContextInstanceMixin` is still there (and is used by
  :class:`~aiogram.utils.i18n.core.I18n` itself). Custom classes built on it migrate
  without changes. What *was* removed is the built-in context on |Bot|, |Dispatcher|
  and Telegram types (see `Dispatcher`_).
- :code:`types.ChatActions` helpers are removed. Use the
  :class:`aiogram.enums.ChatAction` enum with an explicit call, the
  :class:`~aiogram.utils.chat_action.ChatActionSender` helper, or the
  :class:`~aiogram.utils.chat_action.ChatActionMiddleware` with the
  :code:`chat_action` flag:

  .. code-block:: python

      # Version 2.x
      await types.ChatActions.typing()

  .. code-block:: python

      # Version 3.x — plain call
      from aiogram.enums import ChatAction

      await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

      # Version 3.x — keeps sending the action while the block runs
      from aiogram.utils.chat_action import ChatActionSender

      async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
          await long_operation()

      # Version 3.x — via middleware + flag
      from aiogram import flags
      from aiogram.utils.chat_action import ChatActionMiddleware

      router.message.middleware(ChatActionMiddleware())

      @router.message(Command("render"))
      @flags.chat_action("upload_photo")
      async def handler(message: Message) -> None:
          ...

.. _migration-i18n:

I18n
----

The i18n machinery moved from :code:`aiogram.contrib.middlewares.i18n` to
:mod:`aiogram.utils.i18n` and the API changed completely — the v2
:code:`I18nMiddleware` with its :code:`trigger`/:code:`gettext` methods is replaced by
the :class:`~aiogram.utils.i18n.core.I18n` core class plus a set of middlewares:

.. code-block:: python

    # Version 2.x
    from aiogram.contrib.middlewares.i18n import I18nMiddleware

    i18n = I18nMiddleware("mybot", LOCALES_DIR)
    dp.middleware.setup(i18n)
    _ = i18n.gettext

.. code-block:: python

    # Version 3.x
    from aiogram.utils.i18n import I18n, SimpleI18nMiddleware
    from aiogram.utils.i18n import gettext as _

    i18n = I18n(path="locales", default_locale="en", domain="mybot")
    SimpleI18nMiddleware(i18n).setup(dp)

Available middlewares:

- :class:`~aiogram.utils.i18n.middleware.SimpleI18nMiddleware` — locale from the
  user's :code:`language_code`
- :class:`~aiogram.utils.i18n.middleware.ConstI18nMiddleware` — fixed locale
- :class:`~aiogram.utils.i18n.middleware.FSMI18nMiddleware` — locale stored in FSM
- subclass :class:`~aiogram.utils.i18n.middleware.I18nMiddleware` and override
  :code:`get_locale` for custom resolution (e.g. from a database)

Lazy translations are available via :code:`aiogram.utils.i18n.lazy_gettext`.

.. note::

    :class:`~aiogram.utils.i18n.core.I18n` scans and loads locales **in its
    constructor**. A :code:`.po` file without a compiled :code:`.mo` in the configured
    domain raises :code:`RuntimeError` immediately at startup (often at import time) —
    in v2 the same problem surfaced later. Make sure compiling catalogs
    (:code:`pybabel compile -d locales -D mybot`) is part of your build/deploy.


Webhook
=======

- The aiohttp web app configuration has been simplified.
- By default, the ability to upload files has been added when you `make requests in response to updates <https://core.telegram.org/bots/faq#how-can-i-make-requests-in-response-to-updates>`_ (available for webhook only).


Telegram API Server
===================

- The :obj:`server` parameter has been moved from the |Bot| instance to :obj:`api` parameter of the :class:`~aiogram.client.session.base.BaseSession`.
- The constant :obj:`aiogram.bot.api.TELEGRAM_PRODUCTION` has been moved to :obj:`aiogram.client.telegram.PRODUCTION`.


Telegram objects transformation (to dict, to json, from json)
=============================================================

- Methods :code:`TelegramObject.to_object()`, :code:`TelegramObject.to_json()` and :code:`TelegramObject.to_python()`
  have been removed due to the use of `pydantic <https://docs.pydantic.dev/>`_ models.
- :code:`TelegramObject.to_object()` should be replaced by :code:`TelegramObject.model_validate()`
  (`Read more <https://docs.pydantic.dev/2.7/api/base_model/#pydantic.BaseModel.model_validate>`_)
- :code:`TelegramObject.as_json()` should be replaced by :func:`aiogram.utils.serialization.deserialize_telegram_object_to_python`
- :code:`<TelegramObject>.to_python()` should be replaced by :code:`json.dumps(deserialize_telegram_object_to_python(<TelegramObject>))`

Here are some usage examples:

- Creating an object from a dictionary representation of an object

  .. code-block::

    # Version 2.x
    message_dict = {"id": 42, ...}
    message_obj = Message.to_object(message_dict)
    print(message_obj)
    # id=42 name='n' ...
    print(type(message_obj))
    # <class 'aiogram.types.message.Message'>

  .. code-block::

    # Version 3.x
    message_dict = {"id": 42, ...}
    message_obj = Message.model_validate(message_dict)
    print(message_obj)
    # id=42 name='n' ...
    print(type(message_obj))
    # <class 'aiogram.types.message.Message'>

- Creating a json representation of an object

  .. code-block::

    # Version 2.x
    async def handler(message: Message) -> None:
        message_json = message.as_json()
        print(message_json)
        # {"id": 42, ...}
        print(type(message_json))
        # <class 'str'>

  .. code-block::

    # Version 3.x
    async def handler(message: Message) -> None:
        message_json = json.dumps(deserialize_telegram_object_to_python(message))
        print(message_json)
        # {"id": 42, ...}
        print(type(message_json))
        # <class 'str'>

- Creating a dictionary representation of an object

  .. code-block::

    async def handler(message: Message) -> None:
        # Version 2.x
        message_dict = message.to_python()
        print(message_dict)
        # {"id": 42, ...}
        print(type(message_dict))
        # <class 'dict'>

  .. code-block::

    async def handler(message: Message) -> None:
        # Version 3.x
        message_dict = deserialize_telegram_object_to_python(message)
        print(message_dict)
        # {"id": 42, ...}
        print(type(message_dict))
        # <class 'dict'>


ChatMember tools
================

- Now :class:`aiogram.types.chat_member.ChatMember` no longer contains tools to resolve an object with the appropriate status.

  .. code-block::

    # Version 2.x
    from aiogram.types import ChatMember

    chat_member = ChatMember.resolve(**dict_data)

  .. code-block::

    # Version 3.x
    from aiogram.utils.chat_member import ChatMemberAdapter

    chat_member = ChatMemberAdapter.validate_python(dict_data)


- Now :class:`aiogram.types.chat_member.ChatMember` and all its child classes no longer
  contain methods for checking for membership in certain logical groups.
  As a substitute, you can use pre-defined groups or create such groups yourself
  and check their entry using the :func:`isinstance` function

  .. code-block::

    # Version 2.x

    if chat_member.is_chat_admin():
        print("ChatMember is chat admin")

    if chat_member.is_chat_member():
        print("ChatMember is in the chat")

  .. code-block::

    # Version 3.x

    from aiogram.utils.chat_member import ADMINS, MEMBERS

    if isinstance(chat_member, ADMINS):
        print("ChatMember is chat admin")

    if isinstance(chat_member, MEMBERS):
        print("ChatMember is in the chat")

  .. note::
    You also can independently create group similar to ADMINS that fits the logic of your application.

    E.g., you can create a PUNISHED group and include banned and restricted members there!
