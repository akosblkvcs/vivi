'use strict';

// Resolve a CS2 match share code to its demo URL.
//
// Usage:   node resolve.js CSGO-xxxxx-xxxxx-xxxxx-xxxxx-xxxxx
// Prints:  the .dem.bz2 URL to stdout (and nothing else), or exits non-zero
//          with the reason on stderr. This is what bot's DEMO_RESOLVER points at.
//
// Needs a Steam account (a throwaway alt is fine — do not use the one you game
// on). Set STEAM_USER, STEAM_PASS, and STEAM_SHARED_SECRET (the mobile
// authenticator secret, so it can pass Steam Guard headlessly).

const SteamUser = require('steam-user');
const GlobalOffensive = require('globaloffensive');
const SteamTotp = require('steam-totp');

const CS2_APPID = 730;
const TIMEOUT_MS = 90000;

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(1);
}

const shareCode = process.argv[process.argv.length - 1];
if (!shareCode || !shareCode.startsWith('CSGO-')) {
  fail(`not a share code: ${shareCode}`);
}

const accountName = process.env.STEAM_USER;
const password = process.env.STEAM_PASS;
const sharedSecret = process.env.STEAM_SHARED_SECRET;
if (!accountName || !password) {
  fail('STEAM_USER and STEAM_PASS must be set');
}

const timer = setTimeout(() => fail('timed out resolving the demo URL'), TIMEOUT_MS);

const user = new SteamUser();
const cs = new GlobalOffensive(user);

user.on('error', (err) => fail(`steam login failed: ${err.message}`));

user.on('steamGuard', (domain, callback, lastCodeWrong) => {
  if (sharedSecret && !lastCodeWrong) {
    callback(SteamTotp.generateAuthCode(sharedSecret));
  } else {
    fail('Steam Guard code required; set STEAM_SHARED_SECRET (mobile authenticator)');
  }
});

user.on('loggedOn', () => {
  user.setPersona(SteamUser.EPersonaState.Online);
  user.gamesPlayed([CS2_APPID]); // launch CS2 so the Game Coordinator connects
});

cs.on('connectedToGC', () => {
  cs.requestGame(shareCode);
});

cs.on('matchList', (matches) => {
  const match = matches && matches[0];
  const rounds = match && match.roundstatsall;
  // Valve tucks the demo URL into the last round's `map` field.
  const url = rounds && rounds.length ? rounds[rounds.length - 1].map : null;
  if (!url) {
    fail('no demo URL in match info (the demo may have expired)');
  }
  clearTimeout(timer);
  process.stdout.write(`${url}\n`);
  process.exit(0);
});

user.logOn({
  accountName,
  password,
  twoFactorCode: sharedSecret ? SteamTotp.generateAuthCode(sharedSecret) : undefined,
});
