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

.. danger::

    Most breaking changes on this page fall into two groups:
    code that **fails loudly** right after the upgrade (import errors, removed methods)
    and code that **fails silently** — it imports and runs, but misbehaves only on
    specific updates or under specific conditions.
    The silent group is marked with warnings across this page; pay extra attention to it.

.. note::

    Feel free to contribute to this page, if you find something that is not mentioned here.


Dependencies
============

- The dependencies required for :code:`i18n` are no longer part of the default package.
  If your application uses translation functionality, be sure to add an optional dependency:

  :code:`pip install aiogram[i18n]`

  Note that the i18n API itself has also been changed, see :ref:`i18n migration <migration-i18n>` below.

- aiogram 3.x requires a much newer aiohttp than v2 did
  (:code:`aiohttp >= 3.9` at the time of writing — check aiogram's project metadata
  for the current bounds).
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

    import asyncio

    @router.message(Command("slow"))
    async def handler(message: Message) -> None:
        task = asyncio.create_task(do_slow_work(message.chat.id))
        background_tasks.add(task)  # keep a reference, tasks are weakly referenced
        task.add_done_callback(background_tasks.discard)

Note that an exception raised inside a detached task never reaches the aiogram error
handlers — the update is already considered processed by then. Keep a reference to the
task and handle (or at least log) errors inside it yourself.

:code:`AllowedUpdates` helper is removed
----------------------------------------

The v2 helper :code:`aiogram.types.AllowedUpdates` no longer exists.
In v3 pass plain strings or :class:`aiogram.enums.update_type.UpdateType` members,
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
- Added the possibility to register global filters for each router, which helps to reduce code
  repetition and provides an easier way to control the purpose of each router.

.. warning::

    **A bare message handler now receives every content type.**

    In v2, :code:`@dp.message_handler()` without filters was implicitly limited to
    :code:`content_types=ContentType.TEXT` — it received **text messages only**.
    In v3, :code:`@router.message()` without filters receives photos, stickers,
    service messages and everything else as well, and on those updates
    :code:`message.text` is :code:`None`.

    Straightforwardly migrated code like :code:`message.text.lower()` therefore works
    until the first non-text message arrives and then raises
    :code:`AttributeError: 'NoneType' object has no attribute 'lower'`.

    Add the content filter explicitly:

    .. code-block:: python

        # Version 2.x
        @dp.message_handler()
        async def handler(message: types.Message):
            print(message.text.lower())

    .. code-block:: python

        # Version 3.x
        @router.message(F.text)
        async def handler(message: Message) -> None:
            print(message.text.lower())

    Use the matching magic filter for other content types
    (:code:`F.photo`, :code:`F.document`, :code:`F.sticker`, ...), or keep the handler
    unfiltered on purpose and guard every field access.

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

The v2 :code:`Text` filter has no equivalent in v3: it was dropped during the 3.0 beta
cycle (in 3.0.0b8), before the first stable 3.0 release, so it is not available in any
stable 3.x version. Use the magic filter:

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
    - In v3 a handler **without** a :code:`StateFilter`
      (:code:`from aiogram.filters import StateFilter`) runs in **any** state.

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
  For example, the chat type enum is now :class:`aiogram.enums.chat_type.ChatType`
  instead of :code:`aiogram.types.chat.ChatType`.
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

- :code:`bot.kick_chat_member` -> :code:`bot.ban_chat_member`
  (:class:`aiogram.methods.ban_chat_member.BanChatMember`)
- :code:`bot.get_chat_members_count` -> :code:`bot.get_chat_member_count`
  (:class:`aiogram.methods.get_chat_member_count.GetChatMemberCount`)
- :code:`bot.set_sticker_set_thumb` -> :code:`bot.set_sticker_set_thumbnail`
  (:class:`aiogram.methods.set_sticker_set_thumbnail.SetStickerSetThumbnail`)
- :code:`bot.close_bot` -> :code:`bot.close`
  (:class:`aiogram.methods.close.Close`, the Bot API :code:`close` method;
  to close the HTTP client session, use :code:`await bot.session.close()`)
- :code:`bot.download_file_by_id` -> :meth:`~aiogram.client.bot.Bot.download`,
  which accepts both a file id and a :class:`~aiogram.types.file.File`-like object

All other methods follow the current Bot API names — when in doubt, check the method
list in the API reference rather than assuming the v2 name still exists.

Renames and removals inside Telegram types
------------------------------------------

The same applies to shortcuts and fields of the types themselves:

- :code:`chat.kick(...)` -> :meth:`aiogram.types.chat.Chat.ban`
  (:meth:`aiogram.types.chat.Chat.unban` kept its name).
- :code:`ChatPermissions.can_send_media_messages` no longer exists: Bot API 6.5 split it
  into the granular :code:`can_send_audios`, :code:`can_send_documents`,
  :code:`can_send_photos`, :code:`can_send_videos`, :code:`can_send_video_notes` and
  :code:`can_send_voice_notes` flags.

.. warning::

    Telegram types in v3 accept extra fields, so
    :code:`ChatPermissions(can_send_media_messages=True)` does **not** raise a validation
    error. The unknown field is sent to Telegram, ignored there, and the permissions you
    meant to grant are silently not applied. Replace it with the granular flags:

    .. code-block:: python

        # Version 2.x
        permissions = types.ChatPermissions(can_send_media_messages=True)

    .. code-block:: python

        # Version 3.x
        permissions = ChatPermissions(
            can_send_audios=True,
            can_send_documents=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_video_notes=True,
            can_send_voice_notes=True,
        )

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

Positional arguments of API calls now bind to different parameters
-------------------------------------------------------------------

.. warning::

    This is the quiet counterpart of the rule above. **Calls** of Bot API methods and
    of type shortcuts still accept positional arguments — and that is exactly the
    problem. Telegram keeps inserting new parameters into the middle of existing
    signatures, so v2-era positional calls keep working, but every value lands in the
    wrong parameter:

    - The second parameter of :code:`bot.edit_message_text()` is now
      :code:`business_connection_id` (it was :code:`chat_id` in v2), so
      :code:`bot.edit_message_text(text, chat_id, message_id)` sends your chat id as a
      business connection id.
    - The second parameter of :meth:`aiogram.types.message.Message.answer` is now
      :code:`direct_messages_topic_id` (it was :code:`parse_mode` in v2), so
      :code:`message.answer(text, "HTML")` passes the parse mode as a topic id.

    Pass **all** Bot API method arguments as keywords, and audit every positional call
    while migrating:

    .. code-block:: python

        # Version 2.x
        await bot.edit_message_text("New text", chat_id, message_id)
        await message.answer("<b>Hi</b>", "HTML")

    .. code-block:: python

        # Version 3.x
        await bot.edit_message_text(text="New text", chat_id=chat_id, message_id=message_id)
        await message.answer(text="<b>Hi</b>", parse_mode="HTML")


Telegram objects behavior
=========================

Incoming objects are immutable (frozen)
---------------------------------------

Telegram types in v3 are pydantic models, and the types you **receive** from Telegram
are frozen: :code:`Message`, :code:`CallbackQuery`, :code:`User`, :code:`Chat` and every
other subclass of :code:`aiogram.types.base.TelegramObject`. Any code that mutated such
objects in-place (most commonly tests) must be updated:

.. code-block:: python

    # Version 2.x
    message.text = "edited"

.. code-block:: python

    # Version 3.x
    new_message = message.model_copy(update={"text": "edited"})

The "input" types you build yourself and **send** to Telegram remain mutable — they
inherit :code:`aiogram.types.base.MutableTelegramObject` (:code:`frozen=False`):
:class:`~aiogram.types.inline_keyboard_button.InlineKeyboardButton`,
:class:`~aiogram.types.keyboard_button.KeyboardButton`,
the reply markup types,
:class:`~aiogram.types.bot_command.BotCommand`,
:class:`~aiogram.types.message_entity.MessageEntity`,
:class:`~aiogram.types.chat_permissions.ChatPermissions`,
the :code:`InputMedia*` family and others. Assigning to their fields still works.

Optional list fields are :code:`None`, not :code:`[]`
-----------------------------------------------------

.. warning::

    In v2, optional array fields defaulted to empty lists. In v3 they are
    :code:`None` when absent, matching the Bot API. This is not specific to
    :class:`~aiogram.types.message.Message` — it holds for **every** optional array
    field on **every** type, and there are dozens of them across the API.

    Code like :code:`for entity in message.entities:` passes review and works on
    most messages, then raises :code:`TypeError` on the first message without
    entities. The same trap applies to any other type, for example
    :attr:`~aiogram.types.chat.Chat.active_usernames`.
    Always default the value:

    .. code-block:: python

        for entity in message.entities or []:
            ...

        for username in chat.active_usernames or []:
            ...

Objects are compared by value, not by id
-----------------------------------------

.. warning::

    This is a silent breakage with no error message at all.

    In v2, :code:`User.__hash__` returned :code:`self.id` and
    :code:`TelegramObject.__eq__` compared the class plus that hash, so two
    :code:`User` objects describing the same person were **equal regardless of which
    fields were filled in**.

    In v3 there is no custom :code:`__eq__` / :code:`__hash__`: pydantic compares all
    fields, and frozen models hash over the field values. Different API responses fill
    in different subsets of fields — the :code:`from_user` of an update, an entry of
    :code:`get_chat_administrators()` and the result of :code:`get_me()` are all
    different objects for the same user — so comparisons that used to match now
    silently stop matching:

    .. code-block:: python

        # Version 2.x — compared by user id
        if user == await bot.me:
            ...
        if user in await bot.get_chat_administrators(chat_id):
            ...

    .. code-block:: python

        # Version 3.x — compare ids explicitly
        me = await bot.me()
        if user.id == me.id:
            ...

        admins = await bot.get_chat_administrators(chat_id)
        if user.id in {admin.user.id for admin in admins}:
            ...

    The same applies to deduplication: :code:`set[User]` and
    :code:`dict[User, ...]` no longer collapse duplicates of the same user — build the
    set over :code:`user.id` instead.

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

All v3 exception classes live in :code:`aiogram.exceptions`.

- :code:`RetryAfter` -> :class:`~aiogram.exceptions.TelegramRetryAfter`
  (key attribute: :code:`retry_after`, int — renamed from v2 :code:`timeout`)
- :code:`MigrateToChat` -> :class:`~aiogram.exceptions.TelegramMigrateToChat`
  (key attribute: :code:`migrate_to_chat_id`, int — same name as in v2)
- :code:`BadRequest` (and all of its many v2 subclasses)
  -> :class:`~aiogram.exceptions.TelegramBadRequest`
- :code:`NotFound` -> :class:`~aiogram.exceptions.TelegramNotFound`
- :code:`ConflictError` (including :code:`TerminatedByOtherGetUpdates`)
  -> :class:`~aiogram.exceptions.TelegramConflictError`
- :code:`NetworkError` -> :class:`~aiogram.exceptions.TelegramNetworkError`
- :code:`RestartingTelegram` -> :class:`~aiogram.exceptions.RestartingTelegram`,
  now a subclass of :class:`~aiogram.exceptions.TelegramServerError` (any other HTTP 5xx
  response raises :class:`~aiogram.exceptions.TelegramServerError` itself)
- :code:`Unauthorized` -> **split in two**, see below

The v2 :code:`Unauthorized` family covered two different HTTP statuses, and v3 keeps
them apart:

- an invalid or revoked bot token (HTTP 401)
  -> :class:`~aiogram.exceptions.TelegramUnauthorizedError`
- :code:`Forbidden: ...` responses (HTTP 403) — the bot was blocked by the user, kicked
  from the chat, or the user was deactivated, i.e. v2 :code:`BotBlocked`,
  :code:`BotKicked`, :code:`UserDeactivated`, :code:`CantInitiateConversation`
  -> :class:`~aiogram.exceptions.TelegramForbiddenError`

Two v3 classes have no v2 counterpart at all:

- :class:`~aiogram.exceptions.TelegramEntityTooLarge` — HTTP 413, raised for file
  uploads that exceed the server limit
- :class:`~aiogram.exceptions.ClientDecodeError` — raised when the response body cannot
  be decoded; carries :code:`original` (the underlying exception) and :code:`data`
  (the raw response body)

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

v2 shipped around a hundred fine-grained exception classes that were detected by
matching the error text (:code:`MessageNotModified`, :code:`ChatNotFound`, ...).
None of them exist in v3: exceptions are classified **only by the HTTP status code**
of the response, because Telegram does not document stable error codes.

The v2 class hierarchy tells you which v3 class replaces each name — everything that
derived from v2 :code:`BadRequest` is HTTP 400, everything that derived from v2
:code:`Unauthorized` is delivered by Telegram as :code:`Forbidden: ...` with HTTP 403:

- :code:`MessageNotModified` -> :class:`~aiogram.exceptions.TelegramBadRequest`
- :code:`MessageToEditNotFound` -> :class:`~aiogram.exceptions.TelegramBadRequest`
- :code:`MessageToDeleteNotFound` -> :class:`~aiogram.exceptions.TelegramBadRequest`
- :code:`MessageCantBeDeleted` -> :class:`~aiogram.exceptions.TelegramBadRequest`
- :code:`MessageIsTooLong` -> :class:`~aiogram.exceptions.TelegramBadRequest`
- :code:`MessageIdentifierNotSpecified` -> :class:`~aiogram.exceptions.TelegramBadRequest`
- :code:`CantParseEntities` -> :class:`~aiogram.exceptions.TelegramBadRequest`
- :code:`ChatNotFound` -> :class:`~aiogram.exceptions.TelegramBadRequest`
- :code:`InvalidQueryID` -> :class:`~aiogram.exceptions.TelegramBadRequest`
- :code:`InvalidStickersSet` -> :class:`~aiogram.exceptions.TelegramBadRequest`
- :code:`ChatAdminRequired` -> :class:`~aiogram.exceptions.TelegramBadRequest`
- :code:`BotBlocked` -> :class:`~aiogram.exceptions.TelegramForbiddenError`
- :code:`BotKicked` -> :class:`~aiogram.exceptions.TelegramForbiddenError`
- :code:`UserDeactivated` -> :class:`~aiogram.exceptions.TelegramForbiddenError`
- :code:`CantInitiateConversation` -> :class:`~aiogram.exceptions.TelegramForbiddenError`
- :code:`TerminatedByOtherGetUpdates` -> :class:`~aiogram.exceptions.TelegramConflictError`
- :code:`Throttled` -> removed together with the v2 throttling API
  (see :ref:`Throttling <migration-throttling>`)

.. note::

    Because the classification is by status code only, several unrelated v2 names
    collapse into a single v3 class. If you really need to distinguish a specific cause
    inside :class:`~aiogram.exceptions.TelegramBadRequest`, match on the error text:

    .. code-block:: python

        from aiogram.exceptions import TelegramBadRequest

        try:
            await message.edit_text("Same text")
        except TelegramBadRequest as e:
            if "message is not modified" not in e.message:
                raise

    Keep in mind that these texts are not part of the documented Bot API and may change,
    so use the narrowest check you can and always re-raise what you did not expect.


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

The v3 approach is an **inner** middleware, optionally configured per-handler with
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
            if event.from_user is None:  # channel posts have no sender
                return await handler(event, data)

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

.. warning::

    Register this as an **inner** middleware, exactly as shown above
    (:code:`router.message.middleware(...)`), not as an outer one
    (:code:`router.message.outer_middleware(...)`). Handler flags are only available
    after the handler has been resolved, which happens between the outer and the inner
    middleware layers — in an outer middleware :code:`get_flag(data, "rate_limit")`
    always returns :code:`None`, so every per-handler rate would be silently ignored.

.. note::

    The example above keeps timestamps in an unbounded in-memory dict to stay short.
    In production, use a TTL cache or your storage backend, and answer the user
    ("too many requests") instead of dropping silently if that fits your UX.


Keyboard Markup
===============

- Now :class:`aiogram.types.inline_keyboard_markup.InlineKeyboardMarkup`
  and :class:`aiogram.types.reply_keyboard_markup.ReplyKeyboardMarkup` no longer have methods
  for extension, instead you have to use the markup builders
  :class:`aiogram.utils.keyboard.InlineKeyboardBuilder`
  and :class:`aiogram.utils.keyboard.ReplyKeyboardBuilder` respectively
  (:ref:`Read more » <Keyboard builder>`)
- Buttons are constructed with keyword-only arguments now, see
  `Constructors of types and methods are keyword-only`_.


Callbacks data
==============

- The callback data factory is now strictly typed using `pydantic <https://docs.pydantic.dev/>`_ models.
  (:ref:`Read more » <Callback data factory>`)


Finite State machine
====================

- State filters are no longer applied implicitly — see
  `Default state filter behavior is inverted`_.
- Added the possibility to change the FSM strategy. For example,
  if you want to control the state for each user based on chat topics rather than
  the user in a chat, you can specify this in the |Dispatcher|.
- Now :code:`aiogram.fsm.state.State` and :code:`aiogram.fsm.state.StatesGroup` don't have
  helper methods like :code:`.set()`, :code:`.next()`, etc.
  Instead, you should set states by passing them directly to
  :code:`aiogram.fsm.context.FSMContext` (:ref:`Read more » <Finite State Machine>`)
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

    Note also that a topic-aware FSM strategy inserts an extra :code:`thread_id`
    segment into the key (see below), so check the pattern against **real keys taken
    from your traffic**, not only against the shape shown here.

In v3 the storage key layout is controlled by a
:class:`~aiogram.fsm.storage.base.KeyBuilder`. The default
:class:`~aiogram.fsm.storage.base.DefaultKeyBuilder` produces:

.. code-block:: text

    <prefix>:<bot_id?>:<business_connection_id?>:<chat_id>:<thread_id?>:<user_id>:<destiny?>:<field>

The segments marked with :code:`?` are conditional:

- :code:`bot_id` — only with :code:`with_bot_id=True` (off by default)
- :code:`business_connection_id` — only with :code:`with_business_connection_id=True`
  and when the key actually carries one
- :code:`thread_id` — whenever the key carries one, i.e. with the topic-aware FSM
  strategies; this segment is **not** controlled by a builder option
- :code:`destiny` — only with :code:`with_destiny=True`; without it, a non-default
  destiny raises :code:`ValueError` instead of being silently dropped
- :code:`field` — :code:`state`, :code:`data` or :code:`lock`

With the default builder options and the default FSM strategy this reduces to:

.. code-block:: text

    fsm:<chat_id>:<user_id>:state
    fsm:<chat_id>:<user_id>:data

which matches the **default** v2 :code:`RedisStorage2` layout
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
- If you switch the dispatcher to a topic-aware FSM strategy, the keys grow a
  :code:`thread_id` segment and stop matching your v2 keys — that is a separate
  migration, not a drop-in change.
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
  (see :ref:`below <migration-i18n>` and :doc:`Translation </utils/i18n>`)

Other utility changes:

- :code:`aiogram.utils.json` (JSON library selection) is removed without replacement;
  aiogram handles serialization internally.
- :code:`aiogram.utils.mixins` and :code:`ContextInstanceMixin` still exist and custom
  classes built on them migrate unchanged; what *was* removed is the built-in context on
  |Bot|, |Dispatcher| and Telegram types (see `Dispatcher`_).
- :code:`types.ChatActions` helpers are removed. Use the
  :class:`aiogram.enums.chat_action.ChatAction` enum with an explicit call, or the
  :class:`~aiogram.utils.chat_action.ChatActionSender` helper:

  .. code-block:: python

      # Version 2.x
      await types.ChatActions.typing()

  .. code-block:: python

      # Version 3.x
      from aiogram.enums import ChatAction

      await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

  To keep the action alive for the duration of a long operation, use the context
  manager:

  .. code-block:: python

      from aiogram.utils.chat_action import ChatActionSender

      async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
          await long_operation()

  The same thing can be done per handler with
  :class:`~aiogram.utils.chat_action.ChatActionMiddleware` and the
  :code:`@flags.chat_action(...)` decorator, following the same :ref:`flags <flags>`
  mechanism shown in the `Throttling`_ section.

.. _migration-i18n:

I18n
----

The i18n machinery moved from :code:`aiogram.contrib.middlewares.i18n` to
:code:`aiogram.utils.i18n` and the API changed completely — the v2
:code:`I18nMiddleware` with its :code:`trigger`/:code:`gettext` methods is replaced by
the :code:`aiogram.utils.i18n.I18n` core class plus a set of middlewares.
The canonical reference for the v3 API is :doc:`Translation </utils/i18n>`; this section
only covers what changes when you come from v2.

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

    :code:`I18n` scans and loads locales **in its
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
- :code:`<TelegramObject>.as_json()` (returned a :code:`str`) should be replaced by
  :code:`json.dumps(deserialize_telegram_object_to_python(<TelegramObject>))`
- :code:`<TelegramObject>.to_python()` (returned a :code:`dict`) should be replaced by
  :func:`aiogram.utils.serialization.deserialize_telegram_object_to_python`

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
