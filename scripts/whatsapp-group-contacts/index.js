#!/usr/bin/env node
/**
 * Export the members of a WhatsApp group to a CSV file.
 *
 * Usage:
 *   node index.js                      interactive: pick a group from a list
 *   node index.js --list               only print your groups and exit
 *   node index.js --group "Name"       export the group with this exact name
 *   node index.js --group 3            export the 3rd group from --list
 *   node index.js --group "Name" --out members.csv
 *
 * First run shows a QR code: open WhatsApp on your phone,
 * Settings > Linked devices > Link a device, and scan it.
 * The session is saved in ./.wwebjs_auth so later runs don't ask again.
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const qrcode = require('qrcode-terminal');
const { Client, LocalAuth } = require('whatsapp-web.js');

// ---------- CLI args ----------
const argv = process.argv.slice(2);
function flag(name) {
	const i = argv.indexOf(name);
	return i === -1 ? undefined : argv[i + 1];
}
const LIST_ONLY = argv.includes('--list');
const GROUP_ARG = flag('--group');
const OUT_ARG = flag('--out');

if (argv.includes('--help') || argv.includes('-h')) {
	console.log(fs.readFileSync(__filename, 'utf8').split('*/')[0].replace(/^#![^\n]*\n\/\*\*?/, '').replace(/^ \* ?/gm, ''));
	process.exit(0);
}

// ---------- helpers ----------
function csvEscape(value) {
	const s = value == null ? '' : String(value);
	return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function safeFileName(name) {
	return name.replace(/[^\p{L}\p{N}_-]+/gu, '_').replace(/^_+|_+$/g, '') || 'group';
}

function ask(question) {
	const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
	return new Promise((resolve) =>
		rl.question(question, (answer) => {
			rl.close();
			resolve(answer.trim());
		}),
	);
}

async function pickGroup(groups) {
	if (GROUP_ARG !== undefined) {
		const n = Number(GROUP_ARG);
		if (Number.isInteger(n) && n >= 1 && n <= groups.length) return groups[n - 1];
		const byName = groups.find((g) => g.name === GROUP_ARG);
		if (byName) return byName;
		const loose = groups.filter((g) => g.name.toLowerCase().includes(GROUP_ARG.toLowerCase()));
		if (loose.length === 1) return loose[0];
		if (loose.length > 1) {
			console.error(`"${GROUP_ARG}" matches several groups, be more specific:`);
			loose.forEach((g) => console.error(`  - ${g.name}`));
		} else {
			console.error(`No group named "${GROUP_ARG}". Run with --list to see your groups.`);
		}
		return null;
	}
	while (true) {
		const answer = await ask(`\nWhich group? (1-${groups.length}, or q to quit): `);
		if (answer.toLowerCase() === 'q') return null;
		const n = Number(answer);
		if (Number.isInteger(n) && n >= 1 && n <= groups.length) return groups[n - 1];
		console.log('Not a valid number.');
	}
}

// Newer WhatsApp accounts show members as internal "LID" ids instead of phone
// numbers. Try to map those back to numbers when the library supports it.
async function resolveNumbers(client, participants) {
	const map = new Map();
	if (typeof client.getContactLidAndPhone !== 'function') return map;
	const lids = participants.map((p) => p.id._serialized).filter((id) => id.endsWith('@lid'));
	if (lids.length === 0) return map;
	try {
		const pairs = await client.getContactLidAndPhone(lids);
		for (const pair of pairs || []) {
			if (pair && pair.lid && pair.pn) map.set(pair.lid, String(pair.pn).replace(/@.*$/, ''));
		}
	} catch {
		// Not fatal; those rows will just carry the LID instead of a number.
	}
	return map;
}

async function exportGroup(client, group) {
	const chat = await client.getChatById(group.id._serialized);
	const participants = chat.participants || [];
	console.log(`\nExporting "${chat.name}" (${participants.length} members)...`);

	const lidToNumber = await resolveNumbers(client, participants);
	const rows = [];
	for (const p of participants) {
		const id = p.id._serialized;
		let contact = null;
		try {
			contact = await client.getContactById(id);
		} catch {
			// keep going with what we have
		}
		let number = contact && contact.number ? contact.number : '';
		if (!number) number = lidToNumber.get(id) || (id.endsWith('@c.us') ? p.id.user : '');
		rows.push({
			saved_name: contact && contact.name ? contact.name : '',
			profile_name: contact && contact.pushname ? contact.pushname : '',
			number,
			is_admin: p.isAdmin || p.isSuperAdmin ? 'yes' : 'no',
			in_my_contacts: contact && contact.isMyContact ? 'yes' : 'no',
			id,
		});
		process.stdout.write('.');
	}
	process.stdout.write('\n');

	rows.sort((a, b) => (a.saved_name || a.profile_name).localeCompare(b.saved_name || b.profile_name));

	const header = ['saved_name', 'profile_name', 'number', 'is_admin', 'in_my_contacts', 'id'];
	const csv = [header.join(',')]
		.concat(rows.map((r) => header.map((h) => csvEscape(r[h])).join(',')))
		.join('\n');

	const outPath = path.resolve(OUT_ARG || `${safeFileName(chat.name)}.csv`);
	fs.writeFileSync(outPath, '﻿' + csv + '\n', 'utf8'); // BOM so Excel reads UTF-8
	const withNumber = rows.filter((r) => r.number).length;
	console.log(`Wrote ${rows.length} members to ${outPath} (${withNumber} with a phone number).`);
	if (withNumber < rows.length) {
		console.log('Members without a number are hidden by WhatsApp privacy settings; their id is kept.');
	}
}

// ---------- main ----------
const client = new Client({
	authStrategy: new LocalAuth({ dataPath: path.join(__dirname, '.wwebjs_auth') }),
	puppeteer: {
		headless: true,
		args: ['--no-sandbox', '--disable-setuid-sandbox'],
	},
});

client.on('qr', (qr) => {
	console.log('Scan this QR code with WhatsApp (Settings > Linked devices > Link a device):\n');
	qrcode.generate(qr, { small: true });
});

client.on('authenticated', () => console.log('Authenticated.'));
client.on('auth_failure', (msg) => {
	console.error('Authentication failed:', msg);
	process.exit(1);
});

client.on('ready', async () => {
	let exitCode = 0;
	try {
		console.log('Connected. Loading chats...');
		const chats = await client.getChats();
		const groups = chats
			.filter((c) => c.isGroup)
			.sort((a, b) => a.name.localeCompare(b.name));

		if (groups.length === 0) {
			console.log('No groups found on this account.');
		} else {
			console.log(`\nYour groups (${groups.length}):`);
			groups.forEach((g, i) => console.log(`${String(i + 1).padStart(3)}. ${g.name}`));

			if (!LIST_ONLY) {
				const group = await pickGroup(groups);
				if (group) await exportGroup(client, group);
				else exitCode = 1;
			}
		}
	} catch (err) {
		console.error('Error:', err && err.message ? err.message : err);
		exitCode = 1;
	} finally {
		await client.destroy().catch(() => {});
		process.exit(exitCode);
	}
});

client.initialize().catch((err) => {
	console.error('Could not start WhatsApp Web client:', err && err.message ? err.message : err);
	process.exit(1);
});
