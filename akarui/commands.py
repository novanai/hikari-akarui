# MIT License

# Copyright (c) 2023 novanai

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

import typing

import attr
import hikari
from hikari.api import special_endpoints

from . import context

CommandResponseT = (
    special_endpoints.InteractionDeferredBuilder
    | special_endpoints.InteractionMessageBuilder
    | special_endpoints.InteractionModalBuilder
)

CommandCallbackT = typing.Callable[
    [context.Context],
    typing.Awaitable[CommandResponseT],
]


@attr.define
class SlashCommandBuilder(hikari.impl.SlashCommandBuilder):
    callbacks: dict[
        str,
        CommandCallbackT | dict[str, CommandCallbackT | dict[str, CommandCallbackT]],
    ] = attr.field(factory=dict)


@attr.define
class ContextMenuCommandBuilder(hikari.impl.ContextMenuCommandBuilder):
    callbacks: dict[
        str,
        CommandCallbackT | dict[str, CommandCallbackT | dict[str, CommandCallbackT]],
    ] = attr.field(factory=dict)


CommandBuilderT = SlashCommandBuilder | ContextMenuCommandBuilder


class SlashCommandGroup:
    """A slash command group.

    Parameters
    ----------
    name : str
        The name of the command group.
    description : str
        The description of the command group.
    """

    def __init__(self, name: str, description: str) -> None:
        self._builder = SlashCommandBuilder(name=name, description=description)
        self._builder.callbacks[name] = {}

        self._sub_commands: list[SlashCommandBuilder] = []
        self._sub_command_groups: list[SlashSubCommandGroup] = []

    def command(
        self, *sub_groups: SlashSubCommandGroup
    ) -> typing.Callable[[SlashCommandBuilder], None]:
        """Attach a sub command group or a decorated command to this command group.

        Parameters
        ----------
        *sub_groups : SlashSubCommandGroup
            The sub command group(s) to attach to this command group.
        """
        for group in sub_groups:
            self._sub_command_groups.append(group)

        def inner(cmd: SlashCommandBuilder) -> None:
            self._sub_commands.append(cmd)

        return inner

    def settings(
        self,
        default_member_permissions: hikari.UndefinedType
        | int
        | hikari.Permissions = hikari.UNDEFINED,
        is_dm_enabled: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
        is_nsfw: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
        name_localizations: typing.Mapping[hikari.Locale | str, str] | None = None,
        description_localizations: typing.Mapping[hikari.Locale | str, str]
        | None = None,
    ) -> SlashCommandBuilder:
        """Provide settings for this command group.

        Parameters
        ----------
        default_member_permissions : hikari.undefined.UndefinedType | int | hikari.permissions.Permissions
            The default member permissions to utilize this command group by default.

            If ``0``, then it will be available for all members. Note that this doesn't affect
            administrators of the guild and overwrites.
        is_dm_enabled : hikari.UndefinedOr[bool]
            Whether this command group is enabled in DMs with the bot.
        is_nsfw : hikari.UndefinedOr[bool]
            Whether this command group is age-restricted.
        name_localizations : typing.Mapping[hikari.locales.Locale | str, str], optional
            The name localizations to set for this command group.
        description_localizations: typing.Mapping[hikari.locales.Locale | str, str], optional
            The description localizations to set for this command group.
        """
        self._builder.set_default_member_permissions(default_member_permissions)
        self._builder.set_is_dm_enabled(is_dm_enabled)
        self._builder.set_is_nsfw(is_nsfw)
        if name_localizations:
            self._builder.set_name_localizations(name_localizations)
        if description_localizations and isinstance(self._builder, SlashCommandBuilder):
            self._builder.set_description_localizations(description_localizations)

        return self._builder

    def _build(self) -> SlashCommandBuilder:
        for cmd in self._sub_commands:
            opt = hikari.CommandOption(
                type=hikari.OptionType.SUB_COMMAND,
                name=cmd.name,
                description=cmd.description,
                options=cmd.options,
                name_localizations=cmd.name_localizations,
                description_localizations=cmd.description_localizations,
            )
            self._builder.add_option(opt)
            self._builder.callbacks[self._builder.name][cmd.name] = cmd.callbacks[  # type: ignore[index, assignment]
                cmd.name
            ]
        for group in self._sub_command_groups:
            cmd = group._build()
            opt = hikari.CommandOption(
                type=hikari.OptionType.SUB_COMMAND_GROUP,
                name=cmd.name,
                description=cmd.description,
                options=cmd.options,
                name_localizations=cmd.name_localizations,
                description_localizations=cmd.description_localizations,
            )
            self._builder.add_option(opt)
            self._builder.callbacks[self._builder.name][cmd.name] = cmd.callbacks[  # type: ignore[index, assignment]
                cmd.name
            ]

        return self._builder


class SlashSubCommandGroup:
    """A slash sub command group.

    Parameters
    ----------
    name : str
        The name of the sub command group.
    description : str
        The description of the sub command group.
    """

    def __init__(self, name: str, description: str) -> None:
        self._builder = SlashCommandBuilder(name=name, description=description)
        self._builder.callbacks[name] = {}

        self._sub_commands: list[SlashCommandBuilder] = []

    def command(self) -> typing.Callable[[SlashCommandBuilder], None]:
        """Attach a decorated command to this sub command group."""

        def inner(cmd: SlashCommandBuilder) -> None:
            self._sub_commands.append(cmd)

        return inner

    def _build(self) -> SlashCommandBuilder:
        for cmd in self._sub_commands:
            opt = hikari.CommandOption(
                type=hikari.OptionType.SUB_COMMAND,
                name=cmd.name,
                description=cmd.description,
                options=cmd.options,
                name_localizations=cmd.name_localizations,
                description_localizations=cmd.description_localizations,
            )
            self._builder.add_option(opt)
            self._builder.callbacks[self._builder.name][cmd.name] = cmd.callbacks[  # type: ignore[index, assignment]
                cmd.name
            ]

        return self._builder


def slash_command(
    name: str, description: str
) -> typing.Callable[[CommandCallbackT], SlashCommandBuilder]:
    """Convert the decorated function into a slash command.

    Parameters
    ----------
    name : str
        The name of the slash command.
    description : str
        The description of the slash command.
    """

    def inner(func: CommandCallbackT) -> SlashCommandBuilder:
        builder = SlashCommandBuilder(name=name, description=description)
        builder.callbacks[name] = func
        return builder

    return inner


def user_command(
    name: str,
) -> typing.Callable[[CommandCallbackT], ContextMenuCommandBuilder]:
    """Convert the decorated function into a user command.

    Parameters
    ----------
    name : str
        The name of the user command.
    """

    def inner(func: CommandCallbackT) -> ContextMenuCommandBuilder:
        builder = ContextMenuCommandBuilder(name=name, type=hikari.CommandType.USER)
        builder.callbacks[name] = func
        return builder

    return inner


def message_command(
    name: str,
) -> typing.Callable[[CommandCallbackT], ContextMenuCommandBuilder]:
    """Convert the decorated function into a message command.

    Parameters
    ----------
    name : str
        The name of the message command.
    """

    def inner(func: CommandCallbackT) -> ContextMenuCommandBuilder:
        builder = ContextMenuCommandBuilder(name=name, type=hikari.CommandType.MESSAGE)
        builder.callbacks[name] = func
        return builder

    return inner


def settings(
    default_member_permissions: hikari.UndefinedType
    | int
    | hikari.Permissions = hikari.UNDEFINED,
    is_dm_enabled: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
    is_nsfw: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
    name_localizations: typing.Mapping[hikari.Locale | str, str] | None = None,
    description_localizations: typing.Mapping[hikari.Locale | str, str] | None = None,
) -> typing.Callable[[CommandBuilderT], CommandBuilderT]:
    """Provide settings for the decorated command.

    Parameters
    ----------
    default_member_permissions : hikari.undefined.UndefinedType | int | hikari.permissions.Permissions
        The default member permissions to utilize the command by default.

        If ``0``, then it will be available for all members. Note that this doesn't affect
        administrators of the guild and overwrites.
    is_dm_enabled : hikari.UndefinedOr[bool]
        Whether the command is enabled in DMs with the bot.
    is_nsfw : hikari.UndefinedOr[bool]
        Whether the command is age-restricted.
    name_localizations : typing.Mapping[hikari.locales.Locale | str, str], optional
        The name localizations to set for the command.
    description_localizations: typing.Mapping[hikari.locales.Locale | str, str], optional
        The description localizations to set for the command.
    """

    def inner(cmd: CommandBuilderT) -> CommandBuilderT:
        cmd.set_default_member_permissions(default_member_permissions)
        cmd.set_is_dm_enabled(is_dm_enabled)
        cmd.set_is_nsfw(is_nsfw)
        if name_localizations:
            cmd.set_name_localizations(name_localizations)
        if description_localizations and isinstance(cmd, SlashCommandBuilder):
            cmd.set_description_localizations(description_localizations)

        return cmd

    return inner


def option(
    type: hikari.OptionType | int,
    name: str,
    description: str,
    is_required: bool = False,
    choices: typing.Sequence[hikari.CommandChoice] | None = None,
    channel_types: typing.Sequence[hikari.ChannelType | int] | None = None,
    autocomplete: bool = False,
    min_value: int | float | None = None,
    max_value: int | float | None = None,
    name_localizations: typing.Mapping[hikari.Locale | str, str] = {},
    description_localizations: typing.Mapping[hikari.Locale | str, str] = {},
    min_length: int | None = None,
    max_length: int | None = None,
) -> typing.Callable[[SlashCommandBuilder], SlashCommandBuilder]:
    """Add a command option to the decorated command.

    Parameters
    ----------
    type : hikari.commands.OptionType | int
        The type of command option.
    name : str
        The name of the command option.
    description : str
        The description of the command option.
    is_required : bool, optional
        Whether this command option is required.
    choices : typing.Sequence[hikari.commands.CommandChoice], optional
        A sequence of up to (and including) 25 choices for this command.
    channel_types : typing.Sequence[hikari.channels.ChannelType | int], optional
        The channel types that this option will accept.

        If ``None``, then all channel types will be accepted.
    autocomplete : bool, optional
        Whether the option has autocomplete.
    min_value : int | float, optional
        The minimum value permitted (inclusive).
    max_value : int | float, optional
        The maximum value permitted (inclusive).
    name_localizations : typing.Mapping[hikari.locales.Locale | str, str], optional
        A set of name localizations for this option.
    description_localizations : typing.Mapping[hikari.locales.Locale | str, str], optional
        A set of description localizations for this option.
    min_length : int, optional
        The minimum length permitted (inclusive).
    max_length : int, optional
        The maximum length permitted (inclusive).
    """

    def inner(cmd: SlashCommandBuilder) -> SlashCommandBuilder:
        option = hikari.CommandOption(
            type=type,
            name=name,
            description=description,
            is_required=is_required,
            choices=choices,
            channel_types=channel_types,
            autocomplete=autocomplete,
            min_value=min_value,
            max_value=max_value,
            name_localizations=name_localizations,
            description_localizations=description_localizations,
            min_length=min_length,
            max_length=max_length,
        )
        cmd.add_option(option)
        return cmd

    return inner
