#!/usr/bin/env bash
# The Midnight Post Office — self grader 📮
# Run with the stack UP:  docker compose up -d --build  &&  ./check.sh
pass=0; fail=0
ok()   { echo -e "  ✅ $1"; pass=$((pass+1)); }
no()   { echo -e "  ❌ $1"; fail=$((fail+1)); }
try()  { # try "description" "command..."
         if eval "$2" >/dev/null 2>&1; then ok "$1"; else no "$1"; fi; }
tryn() { # must FAIL
         if eval "$2" >/dev/null 2>&1; then no "$1"; else ok "$1"; fi; }

echo -e "\n📮 THE MIDNIGHT POST OFFICE — SELF CHECK\n"

echo "— Part 1: the image —"
try  "image runs as a non-root user" \
     "[ \"\$(docker compose run --rm --no-deps api whoami 2>/dev/null | tr -d '\r')\" != 'root' ]"
try  ".dockerignore exists"            "[ -f .dockerignore ]"
try  "Dockerfile is multi-stage"       "grep -qi 'COPY --from=' Dockerfile"
try  "APP_VERSION is a build ARG"      "grep -qi '^ *ARG APP_VERSION' Dockerfile"

echo -e "\n— Part 2: the stack —"
try  "five services are running" \
     "[ \$(docker compose ps --services --filter status=running | wc -l) -ge 5 ]"
try  "api and postman share ONE image" \
     "[ \$(docker compose images -q api) = \$(docker compose images -q postman) ]"
try  "site is served on :8080"         "curl -fs localhost:8080 -o /dev/null"
tryn "api is NOT published on :5000"   "curl -fs --max-time 3 localhost:5000 -o /dev/null"
tryn "postgres is NOT published"       "curl -fs --max-time 3 localhost:5432 -o /dev/null"
tryn "redis is NOT published"          "curl -fs --max-time 3 localhost:6379 -o /dev/null"
try  "proxy CAN reach api" \
     "docker compose exec -T proxy wget -qO- --timeout=3 http://api:5000/whoami"
tryn "proxy CANNOT reach db (isolation)" \
     "docker compose exec -T proxy wget -qO- --timeout=3 http://db:5432"
tryn "proxy CANNOT reach queue" \
     "docker compose exec -T proxy wget -qO- --timeout=3 http://queue:6379"
try  "db reports healthy" \
     "docker compose ps db | grep -qi healthy"
try  "queue reports healthy" \
     "docker compose ps queue | grep -qi healthy"

echo -e "\n— the end-to-end delivery test —"
NOTE="selfcheck-$$"
curl -fs -X POST -d "note=$NOTE" localhost:8080/send -o /dev/null 2>/dev/null
echo "  ⏳ posted a letter, waiting up to 30s for the postman…"
delivered=0
for i in $(seq 1 30); do
  if curl -fs localhost:8080 | grep -q "delivered by"; then delivered=1; break; fi
  sleep 1
done
[ $delivered -eq 1 ] && ok "a letter went pending → delivered 🎉" \
                     || no "letter never got delivered (check: docker compose logs postman)"
try  "mailroom is shared (api reads postman's files)" \
     "curl -fs localhost:8080/mailroom | grep -q 'letter-'"

echo -e "\n— Part 3: secrets —"
try  "secret file is mounted in api" \
     "docker compose exec -T api test -f /run/secrets/db_password"
tryn "raw password NOT in api's environment" \
     "docker compose exec -T api printenv POSTGRES_PASSWORD"
try  "mailroom is read-only for api (/tamper blocked)" \
     "curl -s localhost:8080/tamper | grep -q blocked"
tryn "no plaintext password in compose.yaml" \
     "grep -qiE '(password|passwd) *: *[\"'\\''a-z0-9]' compose.yaml"
try  "secrets/ is gitignored"          "grep -q 'secrets' .gitignore"
try  ".env is gitignored"              "grep -q '.env' .gitignore"

echo -e "\n— Part 4: dev/prod split —"
try  "compose.override.yaml exists"    "[ -f compose.override.yaml ]"
try  "compose.prod.yaml exists"        "[ -f compose.prod.yaml ]"
try  "prod config is valid" \
     "docker compose -f compose.yaml -f compose.prod.yaml config"
try  "a debug profile exists" \
     "docker compose config --profiles | grep -q debug"

echo -e "\n────────────────────────────"
echo -e "  passed: $pass   failed: $fail"
if [ $fail -eq 0 ]; then
  echo -e "  🎉 every check green. the post office is open. go be smug. 💌\n"
else
  echo -e "  🔧 $fail to go — read the ❌ lines above, they're your to-do list.\n"
fi