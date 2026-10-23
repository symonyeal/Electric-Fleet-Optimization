//! JSON as Python's `json` module reads and writes it.
//!
//! Legend
//!   J ....... a JSON value; objects keep insertion order, as Python dicts do
//!   repr .... Python's `float.__repr__`: shortest round-trip digits, exponent form when the
//!             decimal exponent is below -4 or above 15, at least two exponent digits
//!   dumps ... `json.dumps(x, indent=k)` (k = None: separators ", " and ": ")
//!   canon ... `json.dumps(x, sort_keys=True, separators=(",", ":"))`, the digest form
//!
//! Byte equality with Python matters: digests of scenarios, corridors and artifacts are compared
//! across the two implementations, and stored trajectories hold `Infinity`, which serde_json cannot
//! read or write. Strings are escaped as with `ensure_ascii=True`.

use indexmap::IndexMap;
use std::fmt::Write as _;

pub type Obj = IndexMap<String, J>;

#[derive(Clone, Debug, PartialEq)]
pub enum J {
    Null,
    B(bool),
    I(i64),
    F(f64),
    S(String),
    A(Vec<J>),
    O(Obj),
}

impl J {
    pub fn obj() -> J {
        J::O(Obj::new())
    }

    pub fn get(&self, k: &str) -> Option<&J> {
        match self {
            J::O(o) => o.get(k),
            _ => None,
        }
    }

    /// Value at a dotted path, e.g. "battery.B".
    pub fn at(&self, path: &str) -> Option<&J> {
        path.split('.').try_fold(self, |x, k| x.get(k))
    }

    pub fn f(&self) -> Option<f64> {
        match *self {
            J::F(x) => Some(x),
            J::I(x) => Some(x as f64),
            _ => None,
        }
    }

    pub fn i(&self) -> Option<i64> {
        match *self {
            J::I(x) => Some(x),
            _ => None,
        }
    }

    pub fn s(&self) -> Option<&str> {
        match self {
            J::S(x) => Some(x),
            _ => None,
        }
    }

    pub fn a(&self) -> Option<&Vec<J>> {
        match self {
            J::A(x) => Some(x),
            _ => None,
        }
    }

    pub fn o(&self) -> Option<&Obj> {
        match self {
            J::O(x) => Some(x),
            _ => None,
        }
    }

    pub fn o_mut(&mut self) -> Option<&mut Obj> {
        match self {
            J::O(x) => Some(x),
            _ => None,
        }
    }

    pub fn is_null(&self) -> bool {
        matches!(self, J::Null)
    }

    /// Python truthiness.
    pub fn truthy(&self) -> bool {
        match self {
            J::Null => false,
            J::B(b) => *b,
            J::I(x) => *x != 0,
            J::F(x) => *x != 0.0,
            J::S(s) => !s.is_empty(),
            J::A(a) => !a.is_empty(),
            J::O(o) => !o.is_empty(),
        }
    }

    /// Insert into an object (panics on a non-object: a programming error).
    pub fn set(&mut self, k: &str, v: impl Into<J>) -> &mut J {
        self.o_mut()
            .expect("J::set on a non-object")
            .insert(k.to_string(), v.into());
        self
    }
}

impl From<f64> for J {
    fn from(x: f64) -> J {
        J::F(x)
    }
}
impl From<i64> for J {
    fn from(x: i64) -> J {
        J::I(x)
    }
}
impl From<usize> for J {
    fn from(x: usize) -> J {
        J::I(x as i64)
    }
}
impl From<i32> for J {
    fn from(x: i32) -> J {
        J::I(x as i64)
    }
}
impl From<bool> for J {
    fn from(x: bool) -> J {
        J::B(x)
    }
}
impl From<&str> for J {
    fn from(x: &str) -> J {
        J::S(x.to_string())
    }
}
impl From<String> for J {
    fn from(x: String) -> J {
        J::S(x)
    }
}
impl<T: Into<J>> From<Option<T>> for J {
    fn from(x: Option<T>) -> J {
        x.map_or(J::Null, Into::into)
    }
}
impl<T: Into<J>> From<Vec<T>> for J {
    fn from(x: Vec<T>) -> J {
        J::A(x.into_iter().map(Into::into).collect())
    }
}
impl From<Obj> for J {
    fn from(x: Obj) -> J {
        J::O(x)
    }
}

/// Build an object from (key, value) pairs in order.
#[macro_export]
macro_rules! jo {
    ($($k:expr => $v:expr),* $(,)?) => {{
        #[allow(unused_mut)]
        let mut o = $crate::json::Obj::new();
        $( o.insert(($k).to_string(), $crate::json::J::from($v)); )*
        $crate::json::J::O(o)
    }};
}

/// Python's `repr(float)`.
pub fn repr(x: f64) -> String {
    if x.is_nan() {
        return "NaN".into();
    }
    if x.is_infinite() {
        return if x > 0.0 {
            "Infinity".into()
        } else {
            "-Infinity".into()
        };
    }
    if x == 0.0 {
        return if x.is_sign_negative() {
            "-0.0".into()
        } else {
            "0.0".into()
        };
    }
    // Rust's `{:e}` gives the shortest round-trip digits: "d.ddde-x".
    let e = format!("{:e}", x);
    let (mant, exp) = e.split_once('e').unwrap();
    let exp: i32 = exp.parse().unwrap();
    let neg = mant.starts_with('-');
    let digits: String = mant.chars().filter(|c| c.is_ascii_digit()).collect();
    let decpt = exp + 1; // value = 0.d1d2... x 10^decpt
    let mut s = String::new();
    if neg {
        s.push('-');
    }
    if -4 < decpt && decpt <= 16 {
        let n = digits.len() as i32;
        if decpt <= 0 {
            s.push_str("0.");
            for _ in 0..-decpt {
                s.push('0');
            }
            s.push_str(&digits);
        } else if decpt >= n {
            s.push_str(&digits);
            for _ in 0..decpt - n {
                s.push('0');
            }
            s.push_str(".0");
        } else {
            s.push_str(&digits[..decpt as usize]);
            s.push('.');
            s.push_str(&digits[decpt as usize..]);
        }
    } else {
        s.push_str(&digits[..1]);
        if digits.len() > 1 {
            s.push('.');
            s.push_str(&digits[1..]);
        }
        let _ = write!(s, "e{}{:02}", if exp < 0 { '-' } else { '+' }, exp.abs());
    }
    s
}

fn esc(s: &str, out: &mut String) {
    out.push('"');
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            ' '..='~' => out.push(ch),
            _ => {
                let mut b = [0u16; 2];
                for u in ch.encode_utf16(&mut b) {
                    let _ = write!(out, "\\u{:04x}", u);
                }
            }
        }
    }
    out.push('"');
}

fn write(x: &J, ind: Option<usize>, sort: bool, compact: bool, lvl: usize, out: &mut String) {
    let (isep, ksep) = if compact {
        (",", ":")
    } else if ind.is_some() {
        (",", ": ")
    } else {
        (", ", ": ")
    };
    let nl = |out: &mut String, l: usize| {
        if let Some(k) = ind {
            out.push('\n');
            for _ in 0..k * l {
                out.push(' ');
            }
        }
    };
    match x {
        J::Null => out.push_str("null"),
        J::B(b) => out.push_str(if *b { "true" } else { "false" }),
        J::I(i) => {
            let _ = write!(out, "{i}");
        }
        J::F(f) => out.push_str(&repr(*f)),
        J::S(s) => esc(s, out),
        J::A(a) => {
            if a.is_empty() {
                out.push_str("[]");
                return;
            }
            out.push('[');
            for (k, v) in a.iter().enumerate() {
                if k > 0 {
                    out.push_str(isep);
                }
                nl(out, lvl + 1);
                write(v, ind, sort, compact, lvl + 1, out);
            }
            nl(out, lvl);
            out.push(']');
        }
        J::O(o) => {
            if o.is_empty() {
                out.push_str("{}");
                return;
            }
            out.push('{');
            let mut keys: Vec<&String> = o.keys().collect();
            if sort {
                keys.sort();
            }
            for (k, key) in keys.iter().enumerate() {
                if k > 0 {
                    out.push_str(isep);
                }
                nl(out, lvl + 1);
                esc(key, out);
                out.push_str(ksep);
                write(&o[*key], ind, sort, compact, lvl + 1, out);
            }
            nl(out, lvl);
            out.push('}');
        }
    }
}

/// `json.dumps(x, indent=ind)`.
pub fn dumps(x: &J, ind: Option<usize>) -> String {
    let mut s = String::new();
    write(x, ind, false, false, 0, &mut s);
    s
}

/// `json.dumps(x, sort_keys=True, separators=(",", ":"))`.
pub fn canon(x: &J) -> String {
    let mut s = String::new();
    write(x, None, true, true, 0, &mut s);
    s
}

/// Parse error with byte offset.
#[derive(Debug)]
pub struct ParseErr(pub usize, pub &'static str);

impl std::fmt::Display for ParseErr {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "JSON parse error at byte {}: {}", self.0, self.1)
    }
}
impl std::error::Error for ParseErr {}

struct P<'a> {
    b: &'a [u8],
    k: usize,
}

impl P<'_> {
    fn ws(&mut self) {
        while self.k < self.b.len() && matches!(self.b[self.k], b' ' | b'\n' | b'\r' | b'\t') {
            self.k += 1;
        }
    }
    fn lit(&mut self, s: &str) -> bool {
        if self.b[self.k..].starts_with(s.as_bytes()) {
            self.k += s.len();
            true
        } else {
            false
        }
    }
    fn val(&mut self) -> Result<J, ParseErr> {
        self.ws();
        let Some(&c) = self.b.get(self.k) else {
            return Err(ParseErr(self.k, "end of input"));
        };
        match c {
            b'n' if self.lit("null") => Ok(J::Null),
            b't' if self.lit("true") => Ok(J::B(true)),
            b'f' if self.lit("false") => Ok(J::B(false)),
            b'N' if self.lit("NaN") => Ok(J::F(f64::NAN)),
            b'I' if self.lit("Infinity") => Ok(J::F(f64::INFINITY)),
            b'-' if self.lit("-Infinity") => Ok(J::F(f64::NEG_INFINITY)),
            b'"' => self.str().map(J::S),
            b'[' => {
                self.k += 1;
                let mut a = Vec::new();
                self.ws();
                if self.lit("]") {
                    return Ok(J::A(a));
                }
                loop {
                    a.push(self.val()?);
                    self.ws();
                    if self.lit(",") {
                        continue;
                    }
                    if self.lit("]") {
                        return Ok(J::A(a));
                    }
                    return Err(ParseErr(self.k, "expected , or ]"));
                }
            }
            b'{' => {
                self.k += 1;
                let mut o = Obj::new();
                self.ws();
                if self.lit("}") {
                    return Ok(J::O(o));
                }
                loop {
                    self.ws();
                    let k = self.str()?;
                    self.ws();
                    if !self.lit(":") {
                        return Err(ParseErr(self.k, "expected :"));
                    }
                    let v = self.val()?;
                    o.insert(k, v);
                    self.ws();
                    if self.lit(",") {
                        continue;
                    }
                    if self.lit("}") {
                        return Ok(J::O(o));
                    }
                    return Err(ParseErr(self.k, "expected , or }"));
                }
            }
            _ => self.num(),
        }
    }
    fn num(&mut self) -> Result<J, ParseErr> {
        let s = self.k;
        let mut float = false;
        while self.k < self.b.len() {
            match self.b[self.k] {
                b'0'..=b'9' | b'-' | b'+' => {}
                b'.' | b'e' | b'E' => float = true,
                _ => break,
            }
            self.k += 1;
        }
        let t = std::str::from_utf8(&self.b[s..self.k]).map_err(|_| ParseErr(s, "bad number"))?;
        if t.is_empty() {
            return Err(ParseErr(s, "unexpected character"));
        }
        if float {
            t.parse::<f64>()
                .map(J::F)
                .map_err(|_| ParseErr(s, "bad float"))
        } else {
            match t.parse::<i64>() {
                Ok(i) => Ok(J::I(i)),
                Err(_) => t
                    .parse::<f64>()
                    .map(J::F)
                    .map_err(|_| ParseErr(s, "bad integer")),
            }
        }
    }
    fn hex4(&mut self) -> Result<u32, ParseErr> {
        let h = self
            .b
            .get(self.k..self.k + 4)
            .ok_or(ParseErr(self.k, "short \\u escape"))?;
        let h = std::str::from_utf8(h).map_err(|_| ParseErr(self.k, "bad \\u escape"))?;
        self.k += 4;
        u32::from_str_radix(h, 16).map_err(|_| ParseErr(self.k, "bad \\u escape"))
    }
    fn str(&mut self) -> Result<String, ParseErr> {
        if !self.lit("\"") {
            return Err(ParseErr(self.k, "expected string"));
        }
        let mut s = String::new();
        loop {
            let start = self.k;
            while self.k < self.b.len() && self.b[self.k] != b'"' && self.b[self.k] != b'\\' {
                self.k += 1;
            }
            s.push_str(
                std::str::from_utf8(&self.b[start..self.k])
                    .map_err(|_| ParseErr(start, "bad UTF-8"))?,
            );
            match self.b.get(self.k) {
                None => return Err(ParseErr(self.k, "unterminated string")),
                Some(b'"') => {
                    self.k += 1;
                    return Ok(s);
                }
                _ => {
                    self.k += 1;
                    let e = *self.b.get(self.k).ok_or(ParseErr(self.k, "bad escape"))?;
                    self.k += 1;
                    match e {
                        b'"' => s.push('"'),
                        b'\\' => s.push('\\'),
                        b'/' => s.push('/'),
                        b'n' => s.push('\n'),
                        b'r' => s.push('\r'),
                        b't' => s.push('\t'),
                        b'b' => s.push('\u{8}'),
                        b'f' => s.push('\u{c}'),
                        b'u' => {
                            let mut u = self.hex4()?;
                            if (0xD800..0xDC00).contains(&u) && self.lit("\\u") {
                                let lo = self.hex4()?;
                                u = 0x10000 + ((u - 0xD800) << 10) + (lo - 0xDC00);
                            }
                            s.push(char::from_u32(u).unwrap_or('\u{fffd}'));
                        }
                        _ => return Err(ParseErr(self.k, "bad escape")),
                    }
                }
            }
        }
    }
}

/// `json.loads`.
pub fn loads(s: &str) -> Result<J, ParseErr> {
    let mut p = P {
        b: s.as_bytes(),
        k: 0,
    };
    let v = p.val()?;
    p.ws();
    if p.k != p.b.len() {
        return Err(ParseErr(p.k, "trailing data"));
    }
    Ok(v)
}

/// `json.load(open(path, encoding="utf-8"))`.
pub fn read(path: &std::path::Path) -> Result<J, Box<dyn std::error::Error>> {
    let t = std::fs::read_to_string(path)?;
    Ok(loads(t.strip_prefix('\u{feff}').unwrap_or(&t))?)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn float_repr_matches_python() {
        let cases = [
            (100.0, "100.0"),
            (0.1, "0.1"),
            (1e-5, "1e-05"),
            (0.0001, "0.0001"),
            (1e16, "1e+16"),
            (1e15, "1000000000000000.0"),
            (123456789012345680.0, "1.2345678901234568e+17"),
            (384.67809299999996, "384.67809299999993"),
            (-2.5e-7, "-2.5e-07"),
            (6.7e-5, "6.7e-05"),
            (1.5e300, "1.5e+300"),
            (-0.0, "-0.0"),
        ];
        for (x, s) in cases {
            assert_eq!(repr(x), s, "{x}");
        }
    }

    #[test]
    fn dumps_matches_python_layout() {
        let x = jo! {"a" => vec![1i64, 2], "b" => jo!{}, "c" => Vec::<J>::new(), "é" => "ü\n"};
        assert_eq!(
            dumps(&x, Some(1)),
            "{\n \"a\": [\n  1,\n  2\n ],\n \"b\": {},\n \"c\": [],\n \"\\u00e9\": \"\\u00fc\\n\"\n}"
        );
        assert_eq!(
            dumps(&x, None),
            "{\"a\": [1, 2], \"b\": {}, \"c\": [], \"\\u00e9\": \"\\u00fc\\n\"}"
        );
        assert_eq!(
            canon(&jo! {"b" => 1.0, "a" => J::Null}),
            "{\"a\":null,\"b\":1.0}"
        );
    }

    #[test]
    fn round_trip_with_infinity() {
        let s = "{\"g\": Infinity, \"h\": -Infinity, \"k\": [1, 2.5, \"x\\u00e9\"]}";
        let x = loads(s).unwrap();
        assert_eq!(dumps(&x, None), s);
    }
}
