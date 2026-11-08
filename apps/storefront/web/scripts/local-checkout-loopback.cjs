// Preload only for disposable local checkout QA, never for application releases.
// eslint-disable-next-line @typescript-eslint/no-require-imports -- Node --require installs this guard synchronously before application imports.
const net = require("node:net");
const original = net.Socket.prototype.connect;
const loopback = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);

net.Socket.prototype.connect = function (...args) {
  const supplied = Array.isArray(args[0]) ? args[0] : args;
  const first = supplied[0];
  const options = first && typeof first === "object" ? first : {};
  const isPipe = (typeof first === "string" && first.startsWith("/")) || typeof options.path === "string";
  const host = options.host || (typeof supplied[1] === "string" ? supplied[1] : "localhost");
  if (!isPipe && !loopback.has(host)) throw new Error("Local checkout QA blocks outbound TCP to " + host);
  return original.apply(this, args);
};
