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
    def __init__(self, name: str, description: str) -> None:
        self._builder = SlashCommandBuilder(name=name, description=description)
        self._builder.callbacks[name] = {}

        self._sub_commands: list[SlashCommandBuilder] = []
        self._sub_command_groups: list[SlashSubCommandGroup] = []

    def command(self, sub_group: SlashSubCommandGroup | None = None):
        if sub_group is not None:
            self._sub_command_groups.append(sub_group)

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
    ):
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
    def __init__(self, name: str, description: str) -> None:
        self._builder = SlashCommandBuilder(name=name, description=description)
        self._builder.callbacks[name] = {}

        self._sub_commands: list[SlashCommandBuilder] = []

    def command(self):
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


def slash_command(name: str, description: str):
    def inner(func: CommandCallbackT) -> SlashCommandBuilder:
        builder = SlashCommandBuilder(name=name, description=description)
        builder.callbacks[name] = func
        return builder

    return inner


def user_command(name: str):
    def inner(func) -> ContextMenuCommandBuilder:
        builder = ContextMenuCommandBuilder(name=name, type=hikari.CommandType.USER)
        builder.callbacks[name] = func
        return builder

    return inner


def message_command(name: str):
    def inner(func) -> ContextMenuCommandBuilder:
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
):
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
):
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
