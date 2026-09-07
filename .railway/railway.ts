// Template: set SVE_GITHUB_REPO in the CLI environment before `railway config plan`.
// No secrets belong in this file. See docs/DEPLOYMENT.md before applying.
import { defineRailway, github, postgres, project, service } from "railway/iac";

export default defineRailway((ctx) => {
  const repository = process.env.SVE_GITHUB_REPO;
  if (!repository) throw new Error("Set SVE_GITHUB_REPO=owner/repository before planning.");
  const database = postgres("postgres");
  const backendEnv = {
    ENVIRONMENT: "production", DATA_MODE: "real", ENABLE_MOCK_DATA: "false",
    ENABLE_SIMULATION: "false", SCHEDULER_ENABLED: "false",
    DATABASE_URL: database.env.DATABASE_URL,
    ADMIN_API_TOKEN: ctx.shared.ADMIN_API_TOKEN,
    THE_ODDS_API_KEY: ctx.shared.THE_ODDS_API_KEY,
    SPORTMONKS_API_TOKEN: ctx.shared.SPORTMONKS_API_TOKEN,
    API_FOOTBALL_KEY: ctx.shared.API_FOOTBALL_KEY,
    API_TENNIS_KEY: ctx.shared.API_TENNIS_KEY,
    FOOTBALL_PROVIDER: "sportmonks", TENNIS_PROVIDER: "api_tennis",
    ODDS_PROVIDER: "the_odds_api", ODDS_SYNC_INTERVAL_MINUTES: "30",
    APP_TIMEZONE: "Europe/Berlin", ALLOWED_ORIGINS: ctx.shared.FRONTEND_URL,
    DEPLOYMENT_VERSION: ctx.shared.DEPLOYMENT_VERSION,
  };
  const backend = service("backend", {
    source: github(repository, { rootDirectory: "backend" }),
    preDeploy: "alembic upgrade head",
    healthcheck: "/health", replicas: 1,
    env: { ...backendEnv, PORT: "8000" },
  });
  const worker = service("worker", {
    source: github(repository, { rootDirectory: "backend" }),
    start: "python -m app.jobs.worker", replicas: 1, env: backendEnv,
  });
  const frontend = service("frontend", {
    source: github(repository, { rootDirectory: "frontend" }),
    healthcheck: "/dashboard", replicas: 1,
    env: {
      PORT: "3001", HOSTNAME: "0.0.0.0",
      INTERNAL_API_URL: "http://backend.railway.internal:8000",
      NEXT_PUBLIC_API_URL: ctx.shared.PUBLIC_BACKEND_URL,
      NEXT_PUBLIC_SITE_URL: ctx.shared.FRONTEND_URL,
    },
  });
  return project("sports-value-engine", { resources: [database, backend, worker, frontend] });
});
