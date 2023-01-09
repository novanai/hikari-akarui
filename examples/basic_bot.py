import os
import sys

import hikari
from hikari.impl import rest

import akarui

CLIENT_ID = int(os.environ["CLIENT_ID"])
CLIENT_SECRET = os.environ["CLIENT_SECRET"]

authorization = rest.ClientCredentialsStrategy(
    CLIENT_ID, CLIENT_SECRET, scopes=[hikari.OAuth2Scope.APPLICATIONS_COMMANDS_UPDATE]
)
bot = hikari.RESTBot(authorization)
client = akarui.RESTBotClient.from_restbot(bot)


@client.command()
@akarui.settings(is_dm_enabled=False)
@akarui.option(
    hikari.OptionType.USER,
    "member",
    "Member to get information about.",
    is_required=True,
)
@akarui.slash_command("userinfo", "Get information about a server member.")
async def normal(ctx: akarui.Context) -> hikari.api.InteractionMessageBuilder:
    assert ctx.resolved is not None
    if members := ctx.resolved.members:
        member = list(members.values())[0]
    else:
        return ctx.build_response().set_content("That user is not in this server.")

    embed = (
        hikari.Embed(
            title=f"Member Info - {member.display_name}",
            description=f"ID: `{member.id}`",
        )
        .set_thumbnail(member.avatar_url)
        .add_field(
            "Bot?",
            "Yes" if member.is_bot else "No",
        )
        .add_field(
            "Roles",
            ", ".join(f"<@&{id_}>" for id_ in member.role_ids)
            if member.role_ids
            else "No roles",
        )
    )

    return ctx.build_response().add_embed(embed)


if "--register" in sys.argv:
    client.register_commands(CLIENT_ID, CLIENT_SECRET)

bot.run()
