# Privacy Policy

**Last Updated:** October 7, 2026

## 1. Introduction

This Privacy Policy explains what **Versa** ("the Bot", "we", "us") stores, why, and what you can do about it when you use the Bot on Discord. By using the Bot you agree to the practices described here. This policy applies to the Bot only, not to any Discord server that uses it.

## 2. Information We Collect

### 2.1 Identifiers
- **Discord User IDs** — to attach economy, level, game and moderation data to the right person
- **Server (Guild), Channel, Role, Message and Emoji IDs** — for server settings, giveaways, reaction roles, tickets and logs

We do **not** collect e-mail addresses, IP addresses, passwords, payment details or voice audio.

### 2.2 Data stored when you use Bot features
- **Economy** — virtual wallet and bank balance and the store items in your inventory
- **XP and level** — experience earned from messages (only on servers where leveling is enabled)
- **Flag game score** — number of correct answers
- **Giveaway entries** — your user ID in the list of participants
- **Saved roles** — only if a server turned on *Role Persist*: the role IDs of a member who left, kept up to 60 days so they can be restored if the member returns
- **Moderation records** — warnings, bans, kicks, mutes, timeouts and softbans, each with the reason, the moderator's ID, the time, and the Discord username of the member and of the moderator *at that time*. If a message is sent in a server's *honeypot* channel, the first 150 characters of that message are saved in the reason
- **Scheduled actions** — timers for temporary bans, timed mutes and giveaways (user ID, server ID, due time) until they run
- **Server configuration** — chosen channels, roles, prefix, language, feature switches, store items, reaction roles and the counting channel's current number
- **Bot restrictions** — users and servers that are banned from the Bot, and the Bot's list of trusted staff (ID and username)
- **Tickets** — the ticket owner's ID is written into the ticket channel's topic inside the server

### 2.3 Temporary data (memory only, erased on restart)
AFK status and message, command cooldowns, rate-limit counters and running games.

### 2.4 Messages
The Bot reads messages in servers only to detect commands, award XP and run the counting and honeypot channels. **Ordinary message content is not stored by the Bot.** The exceptions are:
- **Log channels** — if a server enables logging, the Bot posts edited and deleted message content (taken from Discord's short-lived cache) into that server's own staff log channel. It stays inside Discord under the server's control; the Bot does not keep a copy.
- **Direct messages and /modmail** — messages you send to the Bot in DMs or with `/modmail` are forwarded to the Bot owner so you can be answered. The Bot does not save them in its database.
- **Tickets** — ticket conversations stay inside Discord. The Bot does not create or keep transcripts.

## 3. How We Use Your Information

Only to provide Bot features: economy, leveling, games, moderation, tickets, giveaways, polls, reaction roles, counting, honeypot protection, role persist and server settings.

**We do not:**
- sell, rent or share your data with third parties
- use your data for advertising or profiling
- read private conversations

## 4. Where Data Is Stored and Who Can Access It

- Data is stored in a SQLite database on a private virtual server hosted by **Oracle Cloud in Frankfurt, Germany (EU)**.
- A backup of the database is sent once a day as a zip file to the Bot owner's private Discord DMs. **Backups older than 7 days are deleted automatically.**
- Access: the Bot owner. A few trusted staff members may use limited owner commands (for example looking up a Discord account's public details, or adjusting a balance or level). They cannot access the database file.
- The server is protected with key-based SSH access, and the Bot's login token is kept outside the public code.

## 5. Data Retention

- Economy, level, game and giveaway data: kept while the Bot is in use, until you ask us to delete it.
- Finished giveaways: removed after 7 days.
- Saved roles (Role Persist): removed after 60 days.
- Backups: removed after 7 days.
- **Moderation records** (warnings, bans, mutes, timeouts, kicks, case history, Bot bans): kept for the safety of servers. Deleting them on request would let anyone erase their own record, so they are not removed on request. If you think a record is wrong, contact the server's staff or us.
- If the Bot is removed from a server its data is not deleted automatically (it is kept in case the Bot is added again). Server administrators can reset the Bot's configuration with `/setup reset`, and can ask us to remove other server data.

## 6. Your Rights

- **Access** — ask us what the Bot stores about you.
- **Deletion** — ask us and we will delete, from the live database, your **economy profile and inventory, XP and level, flag game score, saved roles, giveaway entries and temporary data**. We aim to do this within 30 days. We cannot delete moderation records (see section 5).
- **Correction** — ask us to correct data that is wrong.

If you are in the EU or UK you also have the rights granted by the GDPR. Our legal basis is our legitimate interest in running and securing the Bot, and the legitimate interest of server communities in keeping moderation records.

To use these rights, contact us on the support server.

## 7. Children's Privacy

You must be old enough to use Discord (at least 13, or higher where your country requires it). We do not knowingly collect data from anyone younger. If you believe a child has given us data, contact us and we will remove it.

## 8. Third-Party Services

- **Discord API** — subject to [Discord's Privacy Policy](https://discord.com/privacy)
- **restcountries.com** — the flag game downloads public country names and flag images; no user data is sent
- **Oracle Cloud** — hosts the server the Bot runs on

## 9. Security

We take reasonable measures to protect stored data. No system is completely secure, so we cannot guarantee absolute security.

## 10. Server Administrators

Administrators who add the Bot to a server are responsible for informing their members about the data the Bot handles, for example by linking this policy.

## 11. Changes to This Policy

We may update this policy. Significant changes will be announced on the support server. The date at the top shows the latest version.

## 12. Contact Us

- **Support Server:** https://discord.gg/hxYWsFVWp8
- **GitHub:** github.com/Takizawa747/versa-bot

---

*This Privacy Policy applies to the Versa Discord Bot.*
