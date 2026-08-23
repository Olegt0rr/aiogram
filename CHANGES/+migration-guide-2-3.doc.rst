Significantly expanded the 2.x -> 3.x migration guide: default bot properties
(:code:`DefaultBotProperties`), :code:`bot.me()` becoming a method, dict-style context
storage on :code:`Bot`/:code:`Dispatcher`, removed background handler execution
(:code:`run_task`), :code:`AllowedUpdates` replacement, throttling migration recipe
(flags + middleware), error handlers (:code:`ErrorEvent`, :code:`ExceptionTypeFilter`),
:code:`chat_type`/:code:`Text` filter replacements, command arguments via
:code:`CommandObject`, keyword-only constructors, frozen models, optional list fields
becoming :code:`None`, model-bound :code:`.bot` context, :code:`forward_origin`,
exception attribute renames, Bot API method renames, FSM storage key builders and live
state migration, concrete :code:`InputFile` classes, relocated/removed utilities and
the new :code:`aiogram.utils.i18n` API.
