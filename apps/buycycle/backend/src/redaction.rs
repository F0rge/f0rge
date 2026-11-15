//! Source credentials are removed before hashing, retaining or deriving observations.
use crate::collector::CollectionError;
use serde_json::Value;

const LIMIT: usize = 32 * 1024 * 1024;
pub(crate) const VERSION: u32 = 1;
fn marker(secret: &str) -> &'static str {
    const NORMAL: &str = "[REDACTED_CREDENTIAL]";
    if !secret.is_empty() && NORMAL.contains(secret) {
        "████"
    } else {
        NORMAL
    }
}
fn text(input: &str, secret: &str) -> Result<String, CollectionError> {
    if secret.is_empty() {
        return Ok(input.to_owned());
    }
    let mut output = String::new();
    let mut position = 0;
    for (index, _) in input.match_indices(secret) {
        if output.len() + index - position + marker(secret).len() > LIMIT {
            return Err(CollectionError::Incomplete);
        }
        output.push_str(&input[position..index]);
        output.push_str(marker(secret));
        position = index + secret.len();
    }
    if output.len() + input.len() - position > LIMIT {
        return Err(CollectionError::Incomplete);
    }
    output.push_str(&input[position..]);
    Ok(output)
}
fn normalized(key: &str) -> String {
    key.chars()
        .filter(char::is_ascii_alphanumeric)
        .flat_map(char::to_lowercase)
        .collect()
}
fn credential_field(key: &str, request_context: bool) -> bool {
    matches!(
        key,
        "apikey"
            | "authorization"
            | "accesstoken"
            | "refreshtoken"
            | "idtoken"
            | "token"
            | "password"
            | "clientsecret"
            | "secret"
            | "cookie"
            | "setcookie"
            | "xapikey"
    ) || (key == "key" && request_context)
}
fn request_field(key: &str) -> bool {
    matches!(
        key,
        "request"
            | "requestmetadata"
            | "requestmeta"
            | "query"
            | "queryparams"
            | "queryparameters"
            | "headers"
            | "credentials"
            | "auth"
            | "authentication"
    )
}
fn walk(
    value: Value,
    secret: &str,
    sensitive: bool,
    request_context: bool,
    budget: &mut usize,
) -> Result<Value, CollectionError> {
    match value {
        Value::String(s) => {
            let safe = if sensitive {
                marker(secret).to_owned()
            } else {
                text(&s, secret)?
            };
            *budget = budget
                .checked_add(safe.len())
                .ok_or(CollectionError::Incomplete)?;
            if *budget > LIMIT {
                return Err(CollectionError::Incomplete);
            }
            Ok(Value::String(safe))
        }
        Value::Array(values) => Ok(Value::Array(
            values
                .into_iter()
                .map(|v| walk(v, secret, sensitive, request_context, budget))
                .collect::<Result<_, _>>()?,
        )),
        Value::Object(values) => {
            let mut safe = serde_json::Map::new();
            for (key, value) in values {
                let field = normalized(&key);
                let mut safe_key = text(&key, secret)?;
                // Keep both fields if redacting an object key causes a collision.
                let separator = (0xE000..=0xF8FF)
                    .filter_map(char::from_u32)
                    .find(|c| !secret.contains(*c))
                    .unwrap_or('█');
                while safe.contains_key(&safe_key) {
                    safe_key.push(separator)
                }
                *budget = budget
                    .checked_add(safe_key.len())
                    .ok_or(CollectionError::Incomplete)?;
                if *budget > LIMIT {
                    return Err(CollectionError::Incomplete);
                }
                let value = walk(
                    value,
                    secret,
                    sensitive || credential_field(&field, request_context),
                    request_context || request_field(&field),
                    budget,
                )?;
                safe.insert(safe_key, value);
            }
            Ok(Value::Object(safe))
        }
        scalar => {
            if sensitive {
                *budget = budget
                    .checked_add(marker(secret).len())
                    .ok_or(CollectionError::Incomplete)?;
                if *budget > LIMIT {
                    return Err(CollectionError::Incomplete);
                }
                Ok(Value::String(marker(secret).to_owned()))
            } else {
                Ok(scalar)
            }
        }
    }
}
pub(crate) fn source(value: Value, secret: &str) -> Result<Value, CollectionError> {
    walk(value, secret, false, false, &mut 0)
}
/// Locate complete JSON fragments inside the Flight protocol without relying on object-key order.
pub(crate) fn fragments(input: &str) -> Result<Vec<Value>, CollectionError> {
    let mut result = Vec::new();
    let mut cursor = 0;
    let mut attempts = 0;
    while let Some(relative) = input[cursor..].find(['{', '[']) {
        attempts += 1;
        if attempts > 4096 {
            return Err(CollectionError::Incomplete);
        }
        let start = cursor + relative;
        let mut stream = serde_json::Deserializer::from_str(&input[start..]).into_iter::<Value>();
        if let Some(Ok(value)) = stream.next() {
            cursor = start + stream.byte_offset();
            result.push(value)
        } else {
            cursor = start + 1;
        }
    }
    Ok(result)
}
fn embedded(input: &str, secret: &str) -> Result<String, CollectionError> {
    let mut output = String::new();
    let mut cursor = 0;
    let mut attempts = 0;
    while let Some(relative) = input[cursor..].find(['{', '[']) {
        attempts += 1;
        if attempts > 4096 {
            return Err(CollectionError::Incomplete);
        }
        let start = cursor + relative;
        output.push_str(&text(&input[cursor..start], secret)?);
        let mut stream = serde_json::Deserializer::from_str(&input[start..]).into_iter::<Value>();
        if let Some(Ok(value)) = stream.next() {
            output.push_str(
                &serde_json::to_string(&source(value, secret)?)
                    .map_err(|_| CollectionError::Incomplete)?,
            );
            cursor = start + stream.byte_offset();
        } else {
            output.push_str(&input[start..start + 1]);
            cursor = start + 1;
        }
        if output.len() > LIMIT {
            return Err(CollectionError::Incomplete);
        }
    }
    output.push_str(&text(&input[cursor..], secret)?);
    if output.len() > LIMIT {
        return Err(CollectionError::Incomplete);
    }
    Ok(output)
}
pub(crate) fn detail_html(html: &str, secret: &str) -> Result<String, CollectionError> {
    let regex = regex::Regex::new(r#"self\.__next_f\.push\(\[1,\"(.*?)\"\]\)</script>"#)
        .expect("constant Flight source regex");
    let captures: Vec<_> = regex.captures_iter(html).collect();
    if captures.len() > 4096 {
        return Err(CollectionError::Incomplete);
    }
    let mut chunks = Vec::new();
    for capture in &captures {
        let decoded: String = serde_json::from_str(&format!("\"{}\"", &capture[1]))
            .map_err(|_| CollectionError::Incomplete)?;
        chunks.push(decoded);
    }
    // Flight is a fragmented logical stream. Credentials and objects may span pushes.
    let safe = embedded(&chunks.concat(), secret)?;
    if !secret.is_empty() && safe.contains(secret) {
        return Err(CollectionError::Incomplete);
    }
    let mut output = String::new();
    let mut cursor = 0;
    let mut logical_cursor = 0;
    for (index, capture) in captures.iter().enumerate() {
        let matched = capture.get(0).expect("whole Flight chunk");
        output.push_str(&text(&html[cursor..matched.start()], secret)?);
        let mut end = if index + 1 == captures.len() {
            safe.len()
        } else {
            (logical_cursor + chunks[index].len()).min(safe.len())
        };
        while !safe.is_char_boundary(end) {
            end -= 1;
        }
        let safe_chunk = &safe[logical_cursor..end];
        logical_cursor = end;
        output.push_str("self.__next_f.push([1,");
        output
            .push_str(&serde_json::to_string(safe_chunk).map_err(|_| CollectionError::Incomplete)?);
        output.push_str("])</script>");
        cursor = matched.end();
        if output.len() > LIMIT {
            return Err(CollectionError::Incomplete);
        }
    }
    output.push_str(&text(&html[cursor..], secret)?);
    if output.len() > LIMIT || !secret.is_empty() && output.contains(secret) {
        return Err(CollectionError::Incomplete);
    }
    Ok(output)
}
