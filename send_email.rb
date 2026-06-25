#!/usr/bin/env ruby
# frozen_string_literal: true

# Sends an email through the Resend API (https://resend.com/docs/api-reference).
#
# Uses only the Ruby standard library — no gems required.
#
# Required env var:
#   RESEND_API_KEY   Your Resend API key (starts with "re_").
#
# Optional env vars (override the defaults below):
#   MAIL_FROM        Sender, e.g. "Daily News <news@yourdomain.com>".
#                    Must be a verified domain in Resend (or onboarding@resend.dev for tests).
#   MAIL_TO          Comma-separated recipient list.
#   MAIL_SUBJECT     Subject line.
#
# Usage:
#   RESEND_API_KEY=re_xxx MAIL_TO=you@example.com ruby send_email.rb
#   RESEND_API_KEY=re_xxx ruby send_email.rb --html template.html.erb

require "net/http"
require "json"
require "uri"

API_ENDPOINT = "https://api.resend.com/emails"

def fetch_api_key
  key = ENV["RESEND_API_KEY"].to_s.strip
  if key.empty?
    abort "Error: RESEND_API_KEY is not set. Get one at https://resend.com/api-keys"
  end
  key
end

# Pick up an optional HTML body from a file (e.g. --html template.html.erb),
# otherwise fall back to a simple inline message.
def build_html
  if (idx = ARGV.index("--html")) && (path = ARGV[idx + 1])
    abort "Error: file not found: #{path}" unless File.exist?(path)
    File.read(path)
  else
    <<~HTML
      <h1>Hello from Daily News 👋</h1>
      <p>This is a test email sent with <strong>Resend</strong> from a Ruby script.</p>
    HTML
  end
end

def send_email(api_key:, from:, to:, subject:, html:)
  uri = URI(API_ENDPOINT)

  payload = {
    from: from,
    to: to,
    subject: subject,
    html: html
  }

  request = Net::HTTP::Post.new(uri)
  request["Authorization"] = "Bearer #{api_key}"
  request["Content-Type"]  = "application/json"
  request.body = JSON.generate(payload)

  http = Net::HTTP.new(uri.host, uri.port)
  http.use_ssl = true

  http.request(request)
end

def main
  api_key = fetch_api_key

  from    = ENV.fetch("MAIL_FROM", "Daily News <onboarding@resend.dev>")
  to      = ENV.fetch("MAIL_TO", "delivered@resend.dev").split(",").map(&:strip)
  subject = ENV.fetch("MAIL_SUBJECT", "Your Daily News briefing")
  html    = build_html

  puts "Sending email…"
  puts "  From:    #{from}"
  puts "  To:      #{to.join(', ')}"
  puts "  Subject: #{subject}"

  response = send_email(
    api_key: api_key,
    from: from,
    to: to,
    subject: subject,
    html: html
  )

  body = begin
    JSON.parse(response.body)
  rescue JSON::ParserError
    response.body
  end

  if response.is_a?(Net::HTTPSuccess)
    id = body.is_a?(Hash) ? body["id"] : nil
    puts "✓ Sent successfully#{id ? " (id: #{id})" : ""}"
  else
    warn "✗ Failed: HTTP #{response.code}"
    warn JSON.pretty_generate(body) rescue warn(body)
    exit 1
  end
end

main if $PROGRAM_NAME == __FILE__
