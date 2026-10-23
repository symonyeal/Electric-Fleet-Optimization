//! Builds the HiGHS submodule (tag v1.12.0, the version SciPy 1.17 bundles) as a static library.

use std::{env, path::Path};

fn main() {
    let src = Path::new("HiGHS");
    if !src.join("highs").exists() {
        panic!("HiGHS source missing: run `git submodule update --init` (crates/efo-highs/HiGHS)");
    }
    let crt = env::var("CARGO_CFG_TARGET_FEATURE").unwrap_or_default();
    let crt = if crt.split(',').any(|f| f == "crt-static") {
        "MultiThreaded"
    } else {
        "MultiThreadedDLL"
    };
    let dst = cmake::Config::new(src)
        .profile("Release")
        .define("FAST_BUILD", "ON")
        .define("BUILD_SHARED_LIBS", "OFF")
        .define("BUILD_CXX_EXE", "OFF")
        .define("BUILD_EXAMPLES", "OFF")
        .define("BUILD_TESTING", "OFF")
        .define("ZLIB", "OFF")
        .define("CMAKE_MSVC_RUNTIME_LIBRARY", crt)
        .define("CMAKE_INTERPROCEDURAL_OPTIMIZATION", "FALSE")
        .build();
    println!("cargo:rustc-link-search=native={}/lib", dst.display());
    println!("cargo:rustc-link-search=native={}/lib64", dst.display());
    println!("cargo:rustc-link-lib=static=highs");
    let t = env::var("TARGET").unwrap();
    if t.contains("apple") {
        println!("cargo:rustc-link-lib=c++");
    } else if t.contains("linux") || t.contains("windows-gnu") {
        println!("cargo:rustc-link-lib=stdc++");
    }
    println!("cargo:rerun-if-changed=HiGHS/Version.txt");
    println!("cargo:rerun-if-changed=build.rs");
}
