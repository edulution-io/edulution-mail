function auth_password_verify(req, pass)

  if req.domain == nil then
    return dovecot.auth.PASSDB_RESULT_USER_UNKNOWN, "No such user"
  end

  if req.user == nil then
    req.user = ''
  end

  respbody = {}

  -- check against keycloak
  local file = io.open("/etc/phpfpm/sogo-sso.pass", "r")
  local content = file:read("*all")

  if content ~= pass then
    local request_body = string.format('{"username":"%s","password":"%s"}', req.user, pass)
    local response_body = {}

    local res, status_code, headers = http.request {
      url = "http://edulution-mail:5000/authenticate",
      method = "POST",
      headers = {
        ["Content-Type"] = "application/json",
        ["Content-Length"] = #request_body
      },
      source = ltn12.source.string(request_body),
      sink = ltn12.sink.table(response_body)
    }

    if status_code == 200 then
      return dovecot.auth.PASSDB_RESULT_OK, ""
    end
    
  end

  return dovecot.auth.PASSDB_RESULT_PASSWORD_MISMATCH, "Failed to authenticate"

end

function auth_passdb_lookup(req)
   return dovecot.auth.PASSDB_RESULT_USER_UNKNOWN, ""
end

function script_init()
  http = require "socket.http"
  http.TIMEOUT = 2
  ltn12 = require "ltn12"
  return 0
end

function script_deinit()
  return 0
end