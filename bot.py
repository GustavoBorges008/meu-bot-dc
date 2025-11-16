# Parte 1
import os
import discord
from discord.ext import commands
from discord.utils import get
from dotenv import load_dotenv
import json
import random
import asyncio
import logging
from datetime import datetime, timedelta

# -----------------------
# CARREGAR TOKEN
# -----------------------
load_dotenv()
TOKEN = os.getenv("TOKEN")  # coloque seu token no .env: TOKEN=seu_token_aqui

# -----------------------
# CONFIGURAÇÃO DO BOT
# -----------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
bot_on = True  # controle de manutenção

# Staff roles (exato)
STAFF_ROLES = ["Dono", "Braço direito do Dono", "comandante"]

def is_staff(member: discord.Member):
    return any(role.name in STAFF_ROLES for role in member.roles)

# -----------------------
# ARQUIVOS DE DADOS
# -----------------------
os.makedirs("data", exist_ok=True)
os.makedirs("logs", exist_ok=True)

ECON_FILE = "data/economia.json"
XP_FILE = "data/xp.json"
DAILY_FILE = "data/daily.json"
WARN_FILE = "data/warns.json"

def load_file(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_economia():
    return load_file(ECON_FILE)
def save_economia(data):
    save_file(ECON_FILE, data)

def load_xp():
    return load_file(XP_FILE)
def save_xp(data):
    save_file(XP_FILE, data)

def load_daily():
    return load_file(DAILY_FILE)
def save_daily(data):
    save_file(DAILY_FILE, data)

def load_warns():
    return load_file(WARN_FILE)
def save_warns(data):
    save_file(WARN_FILE, data)

# -----------------------
# LOGGER (arquivo)
# -----------------------
logging.basicConfig(
    filename=f"logs/bot_{datetime.now().strftime('%Y-%m-%d')}.log",
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
)

@bot.event
async def on_ready():
    logging.info(f"Bot iniciado como {bot.user}")
    print(f"Bot online como {bot.user}")

# -----------------------
# LOJA / ECONOMIA
# -----------------------
shop_items = {
    "vip": {"price": 5000, "role": "vip", "description": "Acesso VIP"},
    "sword": {"price": 1000, "description": "Espada divertida"},
    "potion": {"price": 500, "description": "Poção de vida"}
}
vip_shop_items = {
    "vip_sword": {"price": 3000, "description": "Espada especial VIP"},
    "vip_potion": {"price": 1500, "description": "Poção poderosa VIP"}
}

@bot.command()
async def money(ctx):
    economia = load_economia()
    uid = str(ctx.author.id)
    if uid not in economia:
        economia[uid] = {"coins":0,"vip":False,"items":[],"last_daily":0}
        save_economia(economia)
    await ctx.send(f"👛 {ctx.author.mention} tem {economia[uid]['coins']} moedas")
    logging.info(f"{ctx.author} usou !money")

@bot.command()
async def shop(ctx):
    economia = load_economia()
    uid = str(ctx.author.id)
    vip_status = economia.get(uid,{}).get("vip", False)
    items = shop_items.copy()
    if vip_status:
        items.update(vip_shop_items)
    embed = discord.Embed(title="🛒 Loja", color=discord.Color.green())
    for key, val in items.items():
        embed.add_field(name=key, value=f"Preço: {val['price']}\n{val.get('description','')}", inline=False)
    await ctx.send(embed=embed)
    logging.info(f"{ctx.author} abriu a loja")

@bot.command()
async def buy(ctx, item_name: str):
    economia = load_economia()
    uid = str(ctx.author.id)
    if uid not in economia:
        economia[uid] = {"coins":0,"vip":False,"items":[],"last_daily":0}
    vip_status = economia[uid]["vip"]
    items = shop_items.copy()
    if vip_status:
        items.update(vip_shop_items)
    item = items.get(item_name.lower())
    if not item:
        await ctx.send("❌ Item não encontrado!")
        return
    if economia[uid]["coins"] < item["price"]:
        await ctx.send("❌ Moedas insuficientes!")
        return
    economia[uid]["coins"] -= item["price"]
    if item_name.lower() == "vip":
        economia[uid]["vip"] = True
        role = get(ctx.guild.roles, name="vip")
        if not role:
            role = await ctx.guild.create_role(name="vip", colour=discord.Colour.gold())
        await ctx.author.add_roles(role)
        save_economia(economia)
        await ctx.send(f"🎖 {ctx.author.mention} comprou VIP!")
        logging.info(f"{ctx.author} comprou VIP")
        return
    economia[uid]["items"].append(item_name.lower())
    save_economia(economia)
    await ctx.send(f"🛍 {ctx.author.mention} comprou {item_name}!")
    logging.info(f"{ctx.author} comprou {item_name}")

# -----------------------
# DAILY 24H
# -----------------------
@bot.command()
async def daily(ctx):
    economia = load_economia()
    daily = load_daily()
    uid = str(ctx.author.id)
    now = int(datetime.utcnow().timestamp())
    if uid not in economia:
        economia[uid] = {"coins":0,"vip":False,"items":[],"last_daily":0}
    if uid not in daily:
        daily[uid] = 0
    if now - daily[uid] >= 86400:
        economia[uid]["coins"] += 100
        daily[uid] = now
        save_economia(economia)
        save_daily(daily)
        await ctx.send(f"💰 {ctx.author.mention}, você recebeu 100 moedas!")
        logging.info(f"{ctx.author} pegou daily")
    else:
        restante = 86400 - (now - daily[uid])
        h = restante // 3600
        m = (restante % 3600) // 60
        s = restante % 60
        await ctx.send(f"⏳ Já pegou o daily. Próximo em {h}h {m}m {s}s")

# -----------------------
# XP / RANK (por servidor)
# -----------------------
def add_xp(user_id, guild_id, xp_amount):
    xp_data = load_xp()
    gid = str(guild_id)
    uid = str(user_id)
    if gid not in xp_data:
        xp_data[gid] = {}
    if uid not in xp_data[gid]:
        xp_data[gid][uid] = {"xp":0,"level":1}
    xp_data[gid][uid]["xp"] += xp_amount
    leveled_up = False
    while xp_data[gid][uid]["xp"] >= xp_data[gid][uid]["level"] * 100:
        xp_data[gid][uid]["xp"] -= xp_data[gid][uid]["level"] * 100
        xp_data[gid][uid]["level"] += 1
        leveled_up = True
    save_xp(xp_data)
    return xp_data[gid][uid]["level"], leveled_up

@bot.command()
async def xp(ctx):
    xp_data = load_xp()
    gid = str(ctx.guild.id)
    uid = str(ctx.author.id)
    if gid not in xp_data:
        xp_data[gid] = {}
    if uid not in xp_data[gid]:
        xp_data[gid][uid] = {"xp":0,"level":1}
        save_xp(xp_data)
    data = xp_data[gid][uid]
    await ctx.send(f"{ctx.author.mention} - Level: {data['level']} | XP: {data['xp']}")
    logging.info(f"{ctx.author} usou !xp")

# -----------------------
# MINI-JOGOS (recompensas)
# -----------------------
def add_rewards(user_id, guild_id, coins, xp_amount):
    economia = load_economia()
    uid = str(user_id)
    if uid not in economia:
        economia[uid] = {"coins":0,"vip":False,"items":[],"last_daily":0}
    economia[uid]["coins"] += coins
    save_economia(economia)
    add_xp(user_id, guild_id, xp_amount)

async def send_status(ctx, coins, xp_amount):
    economia = load_economia()
    uid = str(ctx.author.id)
    itens = economia.get(uid, {}).get("items", [])
    itens_texto = ", ".join(itens) if itens else "nenhum item"
    await ctx.send(f"✨ Você ganhou **{coins} moedas** e **{xp_amount} XP**!\n📦 Seus itens: {itens_texto}")

@bot.command()
async def roll(ctx):
    resultado = random.randint(1,6)
    xp_amount = random.randint(5,20)
    coins = random.randint(10,50)
    add_rewards(ctx.author.id, ctx.guild.id, coins, xp_amount)
    lvl, leveled = add_xp(ctx.author.id, ctx.guild.id, 0)
    if leveled:
        await ctx.send(f"🎉 {ctx.author.mention} subiu para o level {lvl}!")
    await ctx.send(f"🎲 {ctx.author.mention} rolou e tirou **{resultado}**!")
    await send_status(ctx, coins, xp_amount)
    logging.info(f"{ctx.author} usou !roll")# Parte 2 (cole abaixo da Parte 1)

# -----------------------
# HELP BONITO e PAINEL
# -----------------------
@bot.command(name="help", aliases=["h","ajuda"])
async def help_command(ctx):
    embed = discord.Embed(title="❓ Painel de Ajuda", description="Lista de comandos disponíveis", color=discord.Color.purple())
    embed.add_field(name="🎮 Mini-jogos", value="`!roll`", inline=False)
    embed.add_field(name="💰 Economia", value="`!daily`, `!money`, `!shop`, `!buy <item>`", inline=False)
    embed.add_field(name="🏆 Rank", value="`!xp`, `!rank`", inline=False)
    embed.add_field(name="📜 Regras", value="`!regras`", inline=False)
    embed.add_field(name="🎫 Tickets", value="`!ticket <motivo>` (abre canal privado) ou use o botão no painel", inline=False)
    embed.add_field(name="🛡 Administração", value="`!paineladm` (apenas staff)", inline=False)
    await ctx.send(embed=embed)
    logging.info(f"{ctx.author} usou !help")

# -----------------------
# VIEW & BUTTON PARA ABRIR TICKET (integração com painel)
# -----------------------
class TicketView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=None)
        self.author = author  # usuário que abriu o painel (para validar se necessário)

    @discord.ui.button(label="Abrir Ticket", style=discord.ButtonStyle.blurple, custom_id="open_ticket_button")
    async def open_ticket(self, button: discord.ui.Button, interaction: discord.Interaction):
        # cria o ticket com a mesma lógica do comando !ticket
        guild = interaction.guild
        member = interaction.user
        # cria categoria TICKETS se não existir
        cat = discord.utils.get(guild.categories, name="TICKETS")
        if not cat:
            cat = await guild.create_category("TICKETS")
        # permissões
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        for rname in STAFF_ROLES:
            role = discord.utils.get(guild.roles, name=rname)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        # cria canal
        channel_name = f"ticket-{member.name}".lower().replace(" ", "-")
        existing = discord.utils.get(guild.text_channels, name=channel_name)
        if existing:
            await interaction.response.send_message(f"Você já tem um ticket aberto: {existing.mention}", ephemeral=True)
            return
        ch = await guild.create_text_channel(channel_name, category=cat, overwrites=overwrites)
        await ch.send(f"🎫 Ticket criado por {member.mention}\nMotivo: Aberto pelo painel (botão)")
        await interaction.response.send_message(f"✅ Ticket criado: {ch.mention}", ephemeral=True)
        logging.info(f"{member} abriu ticket via botão: {ch.name}")
        log_ch = discord.utils.get(guild.text_channels, name="log-ticket")
        if log_ch:
            await log_ch.send(f"🎫 Ticket criado: {ch.mention} por {member.mention} | Aberto via painel (botão)")

@bot.command()
async def painel(ctx):
    # painel de membros (com ticket no painel)
    economia = load_economia()
    uid = str(ctx.author.id)
    coins = economia.get(uid, {}).get("coins", 0)
    xp_data = load_xp()
    gid = str(ctx.guild.id)
    user_info = xp_data.get(gid, {}).get(uid, {"xp":0, "level":1})
    embed = discord.Embed(title=f"📋 Painel de {ctx.author.name}", color=discord.Color.blue())
    embed.add_field(name="💰 Saldo", value=f"{coins} moedas", inline=False)
    embed.add_field(name="⭐ XP / Level", value=f"Level {user_info['level']} | XP {user_info['xp']}", inline=False)
    embed.add_field(name="🛒 Loja", value="Use `!shop` para abrir a loja", inline=False)
    embed.add_field(name="🎫 Ticket", value="Use `!ticket <motivo>` para abrir um ticket privado ou clique no botão abaixo", inline=False)
    embed.add_field(name="📜 Regras", value="Use `!regras`", inline=False)
    view = TicketView(ctx.author)
    await ctx.send(embed=embed, view=view)
    logging.info(f"{ctx.author} abriu o painel")

# -----------------------
# PAINELADM + FUNÇÕES ADICIONAIS
# (NÃO ALTEREI NADA AQUI, mantive exatamente como você pediu)
# -----------------------
@bot.command()
@commands.has_any_role(*STAFF_ROLES)
async def paineladm(ctx):
    embed = discord.Embed(title="🔧 Painel Administrativo", color=discord.Color.orange())
    embed.add_field(name="!criarcanal <nome>", value="Cria um canal de texto", inline=False)
    embed.add_field(name="!warn <@user> <motivo>", value="Adiciona warn a um usuário", inline=False)
    embed.add_field(name="!warnlist <@user>", value="Mostra warns do usuário", inline=False)
    embed.add_field(name="!citar <mensagem>", value="Marca @everyone e envia mensagem (apaga original)", inline=False)
    embed.add_field(name="!limpar <n>", value="Apaga n mensagens", inline=False)
    embed.add_field(name="!kick <@user> <motivo>", value="Expulsa usuário", inline=False)
    embed.add_field(name="!ban <@user> <motivo>", value="Bane usuário", inline=False)
    embed.add_field(name="!mute <@user> <minutos>", value="Mutar usuário por minutos", inline=False)
    embed.add_field(name="!trancar #canal", value="Tranca o canal (impede enviar mensagens)", inline=False)
    embed.add_field(name="!abrir #canal", value="Reabre canal", inline=False)
    embed.add_field(name="!ticket (membros)", value="Comando ticket visível no painel dos membros", inline=False)
    embed.add_field(name="!logcanais", value="Cria canais de logs protegidos", inline=False)
    embed.add_field(name="!desligarbot", value="@everyone aviso de manutenção (desligar)", inline=False)
    embed.add_field(name="!ligarbot", value="@everyone aviso de retorno (ligar)", inline=False)
    await ctx.send(embed=embed)
    logging.info(f"{ctx.author} abriu paineladm")

# -----------------------
# MODERAÇÃO: criar canal, warn, warnlist, citar, limpar, kick, ban, mute, trancar/abrir
# -----------------------
@bot.command()
@commands.has_any_role(*STAFF_ROLES)
async def criarcanal(ctx, *, nome: str):
    guild = ctx.guild
    await guild.create_text_channel(nome)
    await ctx.send(f"Canal **{nome}** criado!")
    logging.info(f"{ctx.author} criou canal {nome}")
    # log em canal de moderação se existir
    ch = discord.utils.get(ctx.guild.text_channels, name="log-moderação")
    if ch:
        await ch.send(f"🛠 Canal criado por {ctx.author.mention}: **{nome}**")

@bot.command()
@commands.has_any_role(*STAFF_ROLES)
async def warn(ctx, member: discord.Member, *, motivo: str = "Sem motivo"):
    warns = load_warns()
    gid = str(ctx.guild.id)
    if gid not in warns:
        warns[gid] = {}
    if str(member.id) not in warns[gid]:
        warns[gid][str(member.id)] = []
    warns[gid][str(member.id)].append({"autor": ctx.author.id, "motivo": motivo, "data": str(datetime.utcnow())})
    save_warns(warns)
    await ctx.send(f"⚠️ {member.mention} recebeu um aviso: {motivo}")
    logging.info(f"{ctx.author} avisou {member}: {motivo}")
    ch = discord.utils.get(ctx.guild.text_channels, name="log-moderação")
    if ch:
        await ch.send(f"⚠️ {member.mention} recebeu warn por {ctx.author.mention}. Motivo: {motivo}")

@bot.command()
@commands.has_any_role(*STAFF_ROLES)
async def warnlist(ctx, member: discord.Member):
    warns = load_warns()
    gid = str(ctx.guild.id)
    lista = warns.get(gid, {}).get(str(member.id), [])
    if not lista:
        await ctx.send(f"{member.mention} não possui avisos.")
        return
    embed = discord.Embed(title=f"Avisos de {member.display_name}", color=discord.Color.orange())
    for i, w in enumerate(lista, start=1):
        autor = ctx.guild.get_member(w["autor"])
        autor_nome = autor.display_name if autor else "Desconhecido"
        embed.add_field(name=f"{i}. Por {autor_nome}", value=f"{w['motivo']} ({w['data']})", inline=False)
    await ctx.send(embed=embed)
    logging.info(f"{ctx.author} consultou warns de {member}")

@bot.command()
@commands.has_any_role(*STAFF_ROLES)
async def citar(ctx, *, mensagem: str):
    await ctx.message.delete()
    await ctx.send(f"@everyone {mensagem}")
    logging.info(f"{ctx.author} usou citar")

@bot.command()
@commands.has_any_role(*STAFF_ROLES)
async def limpar(ctx, quantidade: int = 5):
    deleted = await ctx.channel.purge(limit=quantidade+1)
    msg = await ctx.send(f"🧹 {len(deleted)-1} mensagens apagadas!")
    await asyncio.sleep(4)
    await msg.delete()
    logging.info(f"{ctx.author} limpou {len(deleted)-1} mensagens")
    ch = discord.utils.get(ctx.guild.text_channels, name="log-moderação")
    if ch:
        await ch.send(f"🧹 {ctx.author.mention} apagou {len(deleted)-1} mensagens no {ctx.channel.mention}")

@bot.command()
@commands.has_any_role(*STAFF_ROLES)
async def kick(ctx, member: discord.Member, *, motivo: str = "Sem motivo"):
    await member.kick(reason=motivo)
    await ctx.send(f"🔨 {member.mention} foi expulso. Motivo: {motivo}")
    logging.info(f"{ctx.author} kickou {member}: {motivo}")
    ch = discord.utils.get(ctx.guild.text_channels, name="log-moderação")
    if ch:
        await ch.send(f"🔨 {member.mention} expulso por {ctx.author.mention}. Motivo: {motivo}")

@bot.command()
@commands.has_any_role(*STAFF_ROLES)
async def ban(ctx, member: discord.Member, *, motivo: str = "Sem motivo"):
    await member.ban(reason=motivo)
    await ctx.send(f"⛔ {member.mention} foi banido. Motivo: {motivo}")
    logging.info(f"{ctx.author} baniu {member}: {motivo}")
    ch = discord.utils.get(ctx.guild.text_channels, name="log-moderação")
    if ch:
        await ch.send(f"⛔ {member.mention} banido por {ctx.author.mention}. Motivo: {motivo}")

@bot.command()
@commands.has_any_role(*STAFF_ROLES)
async def mute(ctx, member: discord.Member, minutos: int = 0):
    role = get(ctx.guild.roles, name="Mutado")
    if not role:
        role = await ctx.guild.create_role(name="Mutado")
        for c in ctx.guild.channels:
            await c.set_permissions(role, send_messages=False)
    await member.add_roles(role)
    await ctx.send(f"🔇 {member.mention} foi mutado por {minutos} minutos.")
    logging.info(f"{ctx.author} mutou {member} por {minutos} minutos")
    ch = discord.utils.get(ctx.guild.text_channels, name="log-moderação")
    if ch:
        await ch.send(f"🔇 {member.mention} mutado por {ctx.author.mention} por {minutos} minutos")
    if minutos > 0:
        await asyncio.sleep(minutos * 60)
        await member.remove_roles(role)
        await ctx.send(f"🔊 {member.mention} desmutado.")
        if ch:
            await ch.send(f"🔊 {member.mention} desmutado automaticamente")

@bot.command()
@commands.has_any_role(*STAFF_ROLES)
async def trancar(ctx, canal: discord.TextChannel = None):
    canal = canal or ctx.channel
    await canal.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(f"🔒 Canal {canal.mention} trancado!")
    logging.info(f"{ctx.author} trancou {canal}")
    ch = discord.utils.get(ctx.guild.text_channels, name="log-moderação")
    if ch:
        await ch.send(f"🔒 Canal {canal.mention} trancado por {ctx.author.mention}")

@bot.command()
@commands.has_any_role(*STAFF_ROLES)
async def abrir(ctx, canal: discord.TextChannel = None):
    canal = canal or ctx.channel
    await canal.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(f"🔓 Canal {canal.mention} aberto!")
    logging.info(f"{ctx.author} abriu {canal}")
    ch = discord.utils.get(ctx.guild.text_channels, name="log-moderação")
    if ch:
        await ch.send(f"🔓 Canal {canal.mention} reaberto por {ctx.author.mention}")

# -----------------------
# TICKETS - cria canal privado para autor + staff
# -----------------------
@bot.command()
async def ticket(ctx, *, motivo: str = "Sem motivo"):
    guild = ctx.guild
    # cria categoria TICKETS se não existir
    cat = discord.utils.get(guild.categories, name="TICKETS")
    if not cat:
        cat = await guild.create_category("TICKETS")
    # permissões
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    for rname in STAFF_ROLES:
        role = discord.utils.get(guild.roles, name=rname)
        if role:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    # cria canal
    channel_name = f"ticket-{ctx.author.name}".lower().replace(" ", "-")
    # evita duplicar ticket do mesmo usuário
    existing = discord.utils.get(guild.text_channels, name=channel_name)
    if existing:
        await ctx.send(f"Você já tem um ticket aberto: {existing.mention}")
        return
    ch = await guild.create_text_channel(channel_name, category=cat, overwrites=overwrites)
    await ch.send(f"🎫 Ticket criado por {ctx.author.mention}\nMotivo: {motivo}")
    await ctx.send(f"✅ Ticket criado: {ch.mention}")
    logging.info(f"{ctx.author} criou ticket {ch.name}")
    log_ch = discord.utils.get(guild.text_channels, name="log-ticket")
    if log_ch:
        await log_ch.send(f"🎫 Ticket criado: {ch.mention} por {ctx.author.mention} | Motivo: {motivo}")

@bot.command()
async def closeticket(ctx):
    # só permite autor do ticket ou staff fechar
    if ctx.channel.category and ctx.channel.category.name == "TICKETS":
        # permissões check
        author_name = ctx.channel.name.replace("ticket-", "")
        if ctx.author.name == author_name or is_staff(ctx.author) or ctx.author.guild_permissions.manage_channels:
            await ctx.send("Fechando ticket...")
            logging.info(f"{ctx.author} fechou {ctx.channel.name}")
            log_ch = discord.utils.get(ctx.guild.text_channels, name="log-ticket")
            if log_ch:
                await log_ch.send(f"🎫 Ticket {ctx.channel.mention} fechado por {ctx.author.mention}")
            await ctx.channel.delete()
        else:
            await ctx.send("❌ Você não pode fechar este ticket.")
    else:
        await ctx.send("Este comando só funciona dentro de um canal de ticket.")

# -----------------------
# NOVOS COMANDOS: REGRAS, RANK, TOP100, RESET SEASON
# -----------------------
@bot.command(name="regras")
async def regras(ctx):
    embed = discord.Embed(title="📜 Regras do Servidor", color=discord.Color.blue())
    embed.description = (
        "**• Regras •**\n\n"
        "- ❌ Não tomaremos nenhum tipo de desrespeito ou traição\n\n"
        "- 🗺️ Não divulgar localização da base para ninguém (isso inclui coordenadas ou dar tp para alguém ir para tal)\n\n"
        "- 🤫 Não saiam distribuindo métodos de Farm, segredos ou planos para pessoas alheias\n\n"
        "- 👥 Respeitem todos no servidor independente do cargo\n\n"
        "- 💬 Não spammar nos chat's"
    )
    await ctx.send(embed=embed)
    logging.info(f"{ctx.author} usou !regras")

@bot.command(name="rank")
async def rank(ctx, member: discord.Member = None):
    xp_data = load_xp()
    gid = str(ctx.guild.id)
    if gid not in xp_data or not xp_data[gid]:
        await ctx.send("❌ Nenhum dado de XP encontrado neste servidor.")
        return
    data = xp_data[gid]
    # cria ranking por XP total (usa xp e level à vista)
    ranking = sorted(data.items(), key=lambda x: x[1].get("xp", 0) + x[1].get("level", 0)*1000, reverse=True)
    # se não passou membro, mostra o invocador
    if member is None:
        member = ctx.author
    uid = str(member.id)
    # posição do usuário
    pos = None
    for i, (user_id, vals) in enumerate(ranking, start=1):
        if user_id == uid:
            pos = i
            user_vals = vals
            break
    # embed com top10
    embed = discord.Embed(title=f"🏆 Rank - {ctx.guild.name}", color=discord.Color.gold())
    embed.set_footer(text=f"Pedido por {ctx.author.display_name}")
    # mostrar posição do usuário
    if pos:
        embed.add_field(name=f"🔖 Posição de {member.display_name}", value=f"#{pos} — Level {user_vals['level']} | XP {user_vals['xp']}", inline=False)
    else:
        embed.add_field(name=f"🔖 Posição de {member.display_name}", value="Sem ranking (0 XP)", inline=False)
    # top10
    top_count = min(10, len(ranking))
    text = ""
    shown = 0
    for i, (user_id, vals) in enumerate(ranking, start=1):
        if shown >= top_count:
            break
        user_obj = ctx.guild.get_member(int(user_id))
        name = user_obj.display_name if user_obj else f"Desconhecido ({user_id})"
        text += f"#{i} — {name} • Level {vals['level']} | XP {vals['xp']}\n"
        shown += 1
    embed.add_field(name=f"🏅 Top {top_count}", value=text or "Nenhum dado", inline=False)
    await ctx.send(embed=embed)
    logging.info(f"{ctx.author} usou !rank")

@bot.command(name="top100")
async def top100(ctx):
    xp_data = load_xp()
    gid = str(ctx.guild.id)
    if gid not in xp_data or not xp_data[gid]:
        await ctx.send("❌ Nenhum dado de XP encontrado neste servidor.")
        return
    data = xp_data[gid]
    ranking = sorted(data.items(), key=lambda x: x[1].get("xp", 0) + x[1].get("level", 0)*1000, reverse=True)
    embed = discord.Embed(title=f"📈 Top 100 - {ctx.guild.name}", color=discord.Color.purple())
    out = ""
    for i, (user_id, vals) in enumerate(ranking[:100], start=1):
        user = ctx.guild.get_member(int(user_id))
        name = user.display_name if user else f"Desconhecido ({user_id})"
        out += f"{i}. {name} — Level {vals['level']} | XP {vals['xp']}\n"
    embed.description = out or "Nenhum dado"
    await ctx.send(embed=embed)
    logging.info(f"{ctx.author} usou !top100")

@bot.command(name="resetseason")
@commands.has_permissions(administrator=True)
async def resetseason(ctx, confirm: str = None):
    """
    Uso: !resetseason confirm
    Para evitar resets acidentais, é necessário passar o argumento confirm exatamente: YES
    Ex: !resetseason YES
    """
    if confirm != "YES":
        await ctx.send("⚠️ Para confirmar o reset da season e zerar o XP deste servidor, rode: `!resetseason YES`")
        return
    xp_data = load_xp()
    gid = str(ctx.guild.id)
    if gid in xp_data:
        xp_data[gid] = {}  # zera todos os dados do servidor
        save_xp(xp_data)
        await ctx.send("✅ Season resetada — XP do servidor zerado.")
        logging.info(f"{ctx.author} resetou a season do servidor {ctx.guild.name}")
    else:
        await ctx.send("❌ Não há dados de XP neste servidor.")

# -----------------------
# CRIAR CANAIS DE LOGS (OPÇÃO 1: canais separados)
# -----------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def logcanais(ctx):
    guild = ctx.guild
    cat = discord.utils.get(guild.categories, name="📁 LOGS")
    if not cat:
        cat = await guild.create_category("📁 LOGS")
    # base overwrite: nega para @everyone
    overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    # permite para cada cargo staff
    for rname in STAFF_ROLES:
        role = discord.utils.get(guild.roles, name=rname)
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
    channel_names = [
        "log-bot", "log-comandos", "log-moderação", "log-ticket", "log-mensagens", "log-entradas", "log-saidas"
    ]
    created = []
    for name in channel_names:
        ch = discord.utils.get(guild.text_channels, name=name)
        if not ch:
            ch = await guild.create_text_channel(name, category=cat, overwrites=overwrites)
            created.append(name)
    if created:
        await ctx.send(f"✅ Canais de logs criados: {', '.join(created)}")
        logging.info(f"{ctx.author} criou canais de logs: {created}")
    else:
        await ctx.send("⚠️ Todos os canais de logs já existem.")
        logging.info(f"{ctx.author} tentou criar canais de logs, mas já existiam.")

# -----------------------
# LOGS EM CANAIS (EVENTOS)
# -----------------------
@bot.event
async def on_member_join(member):
    # Novato role
    role = get(member.guild.roles, name="Novato")
    if not role:
        role = await member.guild.create_role(name="Novato")
    await member.add_roles(role)
    # welcome
    sysch = member.guild.system_channel
    if sysch:
        await sysch.send(f"👋 Bem-vindo a guilda juntos seremos os mais fortes, {member.mention}!")
    # log canal
    ch = discord.utils.get(member.guild.text_channels, name="log-entradas")
    if ch:
        await ch.send(f"📥 Entrou: {member.mention} (ID: {member.id})")
    logging.info(f"Membro entrou: {member}")

@bot.event
async def on_member_remove(member):
    ch = discord.utils.get(member.guild.text_channels, name="log-saidas")
    if ch:
        await ch.send(f"📤 Saiu: {member.name} (ID: {member.id})")
    sysch = member.guild.system_channel
    if sysch:
        await sysch.send(f"🛫 Dependendo do que voce fez não sentiremos sua falta, {member.name}!")
    logging.info(f"Membro saiu: {member}")

@bot.event
async def on_command(ctx):
    # quando um comando é executado (evento on_command recebe Context)
    if ctx.guild:
        ch = discord.utils.get(ctx.guild.text_channels, name="log-comandos")
        if ch:
            await ch.send(f"⚙ Comando: `{ctx.command}` usado por {ctx.author.mention} em {ctx.channel.mention}")
    logging.info(f"Comando {ctx.command} usado por {ctx.author} em {getattr(ctx.channel,'name',None)}")

@bot.event
async def on_message(message):
    # já temos a função on_message em Parte1: precisa manter comportamento (XP + process_commands)
    # Aqui adicionamos logging em canal de logs e ao arquivo
    if message.author.bot:
        return
    # log em canal (não logar mensagens dentro canais de log)
    if message.guild:
        if message.channel.name not in ["log-mensagens", "log-comandos", "log-moderação", "log-ticket", "log-entradas", "log-saidas", "log-bot"]:
            ch = discord.utils.get(message.guild.text_channels, name="log-mensagens")
            if ch:
                content = message.content
                # curta proteção para não enviar mensagens gigantes
                if len(content) > 1500:
                    content = content[:1500] + "..."
                await ch.send(f"💬 **{message.author}** em {message.channel.mention}: {content}")
    # registro em arquivo
    logging.info(f"Msg {message.author}#{message.author.discriminator} em {getattr(message.channel,'name',None)}: {message.content}")
    # XP por mensagem (pequeno delay para não flood)
    try:
        add_xp(message.author.id, message.guild.id, random.randint(5,10))
    except Exception as e:
        logging.error(f"Erro ao adicionar xp por mensagem: {e}")
    await bot.process_commands(message)

# -----------------------
# LIGAR / DESLIGAR BOT (com @everyone)
# (mantive suas funções originais e o check global)
# -----------------------
@bot.command()
@commands.has_any_role(*STAFF_ROLES)
async def desligarbot(ctx):
    global bot_on
    bot_on = False
    await ctx.send("@everyone ⚠️ O bot entrou em manutenção e ficará offline para comandos.")
    logging.info(f"{ctx.author} desligou o bot")

@bot.command()
@commands.has_any_role(*STAFF_ROLES)
async def ligarbot(ctx):
    global bot_on
    bot_on = True
    await ctx.send("@everyone ✅ O bot voltou ao ar e está online!")
    logging.info(f"{ctx.author} ligou o bot")

@bot.check
async def check_bot_on(ctx):
    if not bot_on and ctx.command and ctx.command.name not in ["ligarbot", "paineladm"]:
        await ctx.send("❌ O bot está em manutenção e não pode executar comandos.")
        return False
    return True

# -----------------------
# ERROS DE COMANDO (LOG)
# -----------------------
@bot.event
async def on_command_error(ctx, error):
    logging.error(f"Erro no comando '{getattr(ctx.command,'name',None)}' usado por {ctx.author}: {error}")
    # envia mensagem curta ao usuario
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Você não tem permissão para usar esse comando.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Está faltando um argumento.")
    else:
        await ctx.send(f"❌
# -----------------------
# RODAR O BOT
# -----------------------
bot.run(TOKEN)
