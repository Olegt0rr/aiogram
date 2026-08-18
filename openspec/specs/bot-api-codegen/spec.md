# Bot API Layer & Codegen Specification

## Purpose

`aiogram.types`, `aiogram.methods` and `aiogram.enums` mirror the Telegram Bot
API one-to-one. They are **generated** by the `butcher` tool from `.butcher/`
inputs, so keeping the framework current with a new Bot API version is a
regeneration task, not a hand-editing task.

## Requirements

### Requirement: Full Bot API coverage

Every Bot API object, method and enumeration of the supported API version SHALL
have a corresponding generated class.

#### Scenario: Version marker

- **WHEN** `aiogram.__api_version__` is read
- **THEN** it reports the Bot API version the package targets

#### Scenario: New API entity

- **WHEN** Telegram adds an object or method
- **THEN** a matching class appears under `aiogram/types` or `aiogram/methods` after regeneration, with typed fields and docstrings linking to the official docs

### Requirement: Pydantic-backed models

Telegram objects SHALL be pydantic models with validation, aliasing and
serialization of the Bot API wire format.

#### Scenario: Parsing

- **WHEN** a raw API payload is validated into a type
- **THEN** nested objects are constructed recursively and unknown fields are tolerated

#### Scenario: Serialization

- **WHEN** a method object is serialized for a request
- **THEN** unset fields are omitted and enums are rendered as their values

### Requirement: Method objects are callable

Every Bot API method SHALL be representable as an object that can be awaited
through a bot, returned from a handler, or built via the corresponding `Bot`
shortcut.

#### Scenario: Returning from a handler

- **WHEN** a handler returns `SendMessage(chat_id=..., text=...)`
- **THEN** the dispatcher sends it (or answers the webhook with it)

### Requirement: Object shortcuts

Telegram objects SHALL expose ergonomic shortcuts that prefill ids from the
object itself.

#### Scenario: Message shortcuts

- **WHEN** `message.answer(...)`, `message.reply(...)`, `message.delete()` or `message.edit_text(...)` is called
- **THEN** `chat_id` / `message_id` are taken from the message

#### Scenario: Callback query shortcut

- **WHEN** `callback_query.answer(...)` is called
- **THEN** `callback_query_id` is filled automatically

### Requirement: Input file abstractions

Uploading files SHALL be supported from disk, memory, a URL or an existing
`file_id`.

#### Scenario: Local file

- **WHEN** `FSInputFile("photo.jpg")` is passed
- **THEN** the file is streamed as multipart form data

#### Scenario: In-memory and streamed files

- **WHEN** `BufferedInputFile(...)` or `URLInputFile(...)` is passed
- **THEN** the content is uploaded from the buffer or fetched and streamed respectively

### Requirement: Generation is the source of truth

Generated modules SHALL NOT be hand-edited; changes SHALL be made to `.butcher`
inputs (schema, aliases, templates) and applied via the generator.

#### Scenario: Adding a shortcut

- **WHEN** a new object shortcut is needed
- **THEN** it is declared in the relevant `.butcher/**/*.yml` and produced by `butcher apply`, not written directly into `aiogram/types`

#### Scenario: Regeneration flow

- **WHEN** the API is bumped
- **THEN** `butcher parse`, `butcher refresh` and `butcher apply all` are run, followed by lint, type checks and tests

#### Scenario: Parser artifacts

- **WHEN** `.butcher/**/entity.json` differs from expectations
- **THEN** it is regenerated rather than edited, since the parser overwrites it

### Requirement: Changelog for API updates

A Bot API version bump SHALL be accompanied by a changelog fragment describing
the user-visible additions.

#### Scenario: API bump PR

- **WHEN** a Bot API update branch is prepared
- **THEN** `CHANGES/<issue>.misc.rst` summarizes the new objects, methods and fields
