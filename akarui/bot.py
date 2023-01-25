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

import asyncio
import logging

import hikari
import typing

from . import commands, context, errors

logger = logging.getLogger(__name__)


class RESTBotClient:
    """A client to handle interactions.

    Parameters
    ----------
    bot : hikari.impl.rest_bot.RESTBot
        The bot to create a client from.
    """

    def __init__(self, bot: hikari.RESTBot) -> None:
        self._bot = bot

        self._slash_commands: dict[str, commands.SlashCommandBuilder] = {}
        self._user_commands: dict[str, commands.ContextMenuCommandBuilder] = {}
        self._message_commands: dict[str, commands.ContextMenuCommandBuilder] = {}

        self._bot.set_listener(hikari.CommandInteraction, self._handle_interaction)

    @classmethod
    def from_restbot(cls, bot: hikari.RESTBot) -> RESTBotClient:
        """Create a RESTBotClient instance from a :obj:`~hikari.impl.rest_bot.RESTBot` instance.

        Parameters
        ----------
        bot : hikari.impl.rest_bot.RESTBot
            The bot to create a client from.

        Returns
        -------
        RESTBotClient
            The client.
        """
        return cls(bot)

    def command(self, *groups: commands.SlashCommandGroup)  -> typing.Callable[[commands.CommandBuilderT], None]:
        """Attach a command or slash command group to the client.

        Parameters
        ----------
        *groups : commands.SlashCommandGroup
            The group(s) to attach to the client.
        """
        for group in groups:
            cmd = group._build()
            self._slash_commands[cmd.name] = cmd

        def inner(cmd: commands.CommandBuilderT) -> None:
            if isinstance(cmd, commands.SlashCommandBuilder):
                self._slash_commands[cmd.name] = cmd
            elif (
                isinstance(cmd, commands.ContextMenuCommandBuilder)
                and cmd.type == hikari.CommandType.USER
            ):
                self._user_commands[cmd.name] = cmd
            elif (
                isinstance(cmd, commands.ContextMenuCommandBuilder)
                and cmd.type == hikari.CommandType.MESSAGE
            ):
                self._message_commands[cmd.name] = cmd

        return inner

    def _gather_commands(self) -> dict[int | None, list[commands.CommandBuilderT]]:
        cmds: dict[int | None, list[commands.CommandBuilderT]] = {}

        builders: list[commands.CommandBuilderT] = [
            *self._slash_commands.values(),
            *self._user_commands.values(),
            *self._message_commands.values(),
        ]

        for cmd in builders:
            if cmd.guilds:
                for guild in cmd.guilds:
                    id_ = guild.id if isinstance(guild, hikari.PartialGuild) else guild
                    if id_ in cmds:
                        cmds[id_].append(cmd)
                    else:
                        cmds[id_] = [cmd]
            elif None in cmds:
                cmds[None].append(cmd)
            else:
                cmds[None] = [cmd]

        return cmds

    async def _register_commands(self, client_id: int, client_secret: str) -> None:
        app = hikari.RESTApp()
        await app.start()

        async with app.acquire(None) as rest:
            token = await rest.authorize_client_credentials_token(
                client_id,
                client_secret,
                [hikari.OAuth2Scope.APPLICATIONS_COMMANDS_UPDATE],
            )

        async with app.acquire(token.access_token, "Bearer") as rest:
            commands = self._gather_commands()

            builders: list[commands.CommandBuilderT] = [ # type: ignore[name-defined]
                *self._slash_commands.values(),
                *self._user_commands.values(),
                *self._message_commands.values(),
            ]

            logger.info(
                f"Registering {len(builders)} commands: "
                + ", ".join(f"'{cmd.name}'" for cmd in builders)
            )

            for guild_id, cmds in commands.items():
                await rest.set_application_commands(
                    client_id,
                    cmds,
                    guild_id or hikari.UNDEFINED,
                )

        await app.close()

    def register_commands(self, client_id: int, client_secret: str) -> None:
        """Register all commands attached to the client.

        Parameters
        ----------
        client_id : int
            The application's client ID.
        client_secret : str
            The application's client secret.
        """
        asyncio.run(self._register_commands(client_id, client_secret))

    async def _handle_interaction(
        self,
        event: hikari.CommandInteraction,
    ) -> commands.CommandResponseT:
        cmd: commands.CommandBuilderT | None = None

        if event.command_type == hikari.CommandType.SLASH:
            cmd = self._slash_commands.get(event.command_name)
        elif event.command_type == hikari.CommandType.USER:
            cmd = self._user_commands.get(event.command_name)
        if event.command_type == hikari.CommandType.MESSAGE:
            cmd = self._message_commands.get(event.command_name)

        if cmd:
            callback, _type = self._get_callback_and_type(event, cmd)
            context = self._create_context(event, _type)
            return await callback(context)

        else:
            raise errors.CommandNotFoundError(
                f"Callback for command '{event.command_name}' does not exist."
            )

    def _get_callback_and_type(
        self, event: hikari.CommandInteraction, command: commands.CommandBuilderT
    ) -> tuple[commands.CommandCallbackT, hikari.OptionType | None]:
        if event.command_type in {hikari.CommandType.USER, hikari.CommandType.MESSAGE}:
            return (  # type: ignore[return-value]
                command.callbacks[event.command_name],
                None,
            )

        if not event.options:
            return (  # type: ignore[return-value]
                command.callbacks[event.command_name],
                None,
            )

        elif (opt := event.options[0]).type == hikari.OptionType.SUB_COMMAND:
            return (  # type: ignore[return-value]
                command.callbacks[event.command_name][opt.name],  # type: ignore[index]
                hikari.OptionType.SUB_COMMAND,
            )

        elif (group := event.options[0]).type == hikari.OptionType.SUB_COMMAND_GROUP:
            return (
                command.callbacks[event.command_name][group.name][group.options[0].name],  # type: ignore[index]
                hikari.OptionType.SUB_COMMAND_GROUP,
            )

        else:
            return (  # type: ignore[return-value]
                command.callbacks[event.command_name],
                None,
            )

    def _create_context(
        self, event: hikari.CommandInteraction, cmd_type: hikari.OptionType | None
    ) -> context.Context:
        if cmd_type == hikari.OptionType.SUB_COMMAND:
            assert event.options is not None
            options = event.options[0].options
        elif cmd_type == hikari.OptionType.SUB_COMMAND_GROUP:
            assert event.options is not None
            assert event.options[0].options is not None
            options = event.options[0].options[0].options
        else:
            options = event.options

        return context.Context(
            app=event.app,
            id=event.id,
            application_id=event.application_id,
            type=event.type,
            token=event.token,
            version=event.version,
            channel_id=event.channel_id,
            guild_id=event.guild_id,
            guild_locale=event.guild_locale,
            member=event.member,
            user=event.user,
            locale=event.locale,
            command_id=event.command_id,
            command_name=event.command_name,
            command_type=event.command_type,
            app_permissions=event.app_permissions,
            options=options,
            resolved=event.resolved,
            target_id=event.target_id,
        )
