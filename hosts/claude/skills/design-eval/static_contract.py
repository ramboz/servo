"""Finite static-source-contract APP observations, not visual-quality scoring."""

import os
import sys

if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.pycache_prefix = os.path.join(
        os.environ.get("TMPDIR", "/tmp"), "servo-static-source-only-" + str(os.getpid())
    )
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import importlib
import importlib.metadata
import importlib.util
import platform
import re
import secrets
import shutil
import site
from pathlib import Path

import evidence_io as bundle
import static_snapshot as snapshot
from evidence_io import canonical, require

VERSION = "static-source-contract-app/1"
FAMILY_NORMALIZER = "css-computed-family-list/1"
GENERICS = (
    "serif",
    "sans-serif",
    "monospace",
    "cursive",
    "fantasy",
    "system-ui",
    "ui-serif",
    "ui-sans-serif",
    "ui-monospace",
    "ui-rounded",
    "math",
    "fangsong",
)
RESERVED = ("inherit", "initial", "unset", "revert", "revert-layer", "default", "emoji")
_IDENT = r"(?:[A-Za-z_]|-[A-Za-z_])[A-Za-z0-9_-]*"


def family(value):
    """APP/1 grammar; source C0 remains owned by the pinned producer."""
    require(
        type(value) is str
        and value.isascii()
        and all(ord(c) >= 32 or c == "\t" for c in value)
        and "\\" not in value,
        "unsupported APP family grammar",
    )
    result = []
    for part in value.split(","):
        token = part.strip(" \t")
        if re.fullmatch(r"""(["'])[A-Za-z][A-Za-z0-9 -]*\1""", token):
            result.append({"kind": "named", "value": token[1:-1]})
            continue
        require(
            re.fullmatch(_IDENT + r"(?:[ \t]+" + _IDENT + r")*", token) is not None,
            "unsupported APP family token: " + token,
        )
        words = token.split()
        require(
            not any(word.lower() in RESERVED for word in words),
            "reserved/unsupported APP family token: " + token,
        )
        generic = token.lower() in GENERICS
        require(
            len(words) == 1 or not any(word.lower() in GENERICS for word in words),
            "generic inside multiword APP family",
        )
        result.append(
            {
                "kind": "generic" if generic else "named",
                "value": token.lower() if generic else " ".join(words),
            }
        )
    return result


APP_NORMALIZERS = {
    "presence": "unique-scoped-visible-presence-app/1",
    "text": "text-content-exact-visible-app/1",
    "background-color": "rgba8-exact-v0",
    "color": "rgba8-exact-v0",
    "font-family": FAMILY_NORMALIZER,
    "font-size": "css-scalar-v0",
    "font-weight": "css-scalar-v0",
    "width": "dom-bounds-csspx-v0",
    "height": "dom-bounds-csspx-v0",
}
RAW_KEYS = {
    "presence": None,
    "text": "text",
    "width": "width",
    "height": "height",
    "background-color": "backgroundColor",
    "color": "color",
    "font-family": "fontFamily",
    "font-size": "fontSize",
    "font-weight": "fontWeight",
}


def compare(core, observation, producer):
    policies, targets, ids = core["policy"], core["facts"], core["inventory"]
    require(
        ids == sorted(set(ids))
        and [r["id"] for r in policies] == ids
        and [r["id"] for r in targets] == ids,
        "static required inventory mismatch",
    )
    result = []
    for policy, target in zip(policies, targets):
        prop = policy["property"]
        node = observation["elements"].get(policy["element"])
        value, raw = None, None
        settlement = observation.get("settlement") or {}
        if policy["id"] in settlement.get("unstable_ids", []):
            status, reason = "unknown", "required observation/correspondence did not settle"
        elif node is None or type(node.get("count")) is not int or node["count"] not in (0, 1):
            status, reason = (
                "unknown",
                node.get("error")
                if node and node.get("error")
                else "missing/ambiguous approved bound-element observation",
            )
        elif node.get("error"):
            status, reason = "unknown", node["error"]
        elif node.get("count") == 0 or node.get("visible") is False:
            status, reason = "fail", "approved bound element absent or not visible"
        elif type(node.get("visible")) is not bool:
            status, reason = "unknown", "missing explicit bound-element visibility observation"
        elif prop == "text" and type(node.get("raw", {}).get("textVisible")) is not bool:
            status, reason = "unknown", "missing explicit text-paint observation"
        elif (
            prop == "text"
            and type(node["raw"].get("text")) is str
            and node["raw"]["text"].strip()
            and not node["raw"]["textVisible"]
        ):
            status, reason = (
                "fail",
                "approved bound text lacks a positive-area witness for each non-whitespace range",
            )
        else:
            try:
                require(prop in APP_NORMALIZERS, "unsupported static property")
                raw = True if prop == "presence" else node["raw"][RAW_KEYS[prop]]
                if prop == "font-family":
                    value = family(raw)
                elif prop in ("presence", "text"):
                    require(
                        type(raw) is (bool if prop == "presence" else str),
                        "invalid static observation type",
                    )
                    value = raw
                else:
                    require(producer is not None, "source normalizer unavailable")
                    value = producer.normalize(prop, raw)
                require(type(policy.get("tolerance")) is str, "missing explicit tolerance")
                if policy["comparison"] in ("exact", "present"):
                    require(policy["tolerance"] == "0", "unsupported exact tolerance")
                    matches = canonical(value) == canonical(target["value"])
                elif policy["comparison"] == "absolute-inclusive":
                    require(producer is not None, "source scalar comparator unavailable")
                    matches = producer.within(str(value), str(target["value"]), policy["tolerance"])
                else:
                    raise ValueError("unsupported static comparison")
                status = "pass" if matches else "fail"
                reason = "approved comparison satisfied" if matches else "observed value differs"
            except (ValueError, KeyError, TypeError) as exc:
                status, reason = "unknown", str(exc)
        acquisition_error = observation.get("acquisition_error", observation.get("error"))
        if acquisition_error and status != "fail":
            status, reason = "unknown", acquisition_error
        result.append(
            {
                **policy,
                "required": True,
                "app_normalizer": APP_NORMALIZERS.get(prop),
                "raw": raw,
                "actual": value,
                "expected": target["value"],
                "observation": {
                    "path": "observations.json",
                    "role": policy["element"],
                    "property": prop,
                },
                "status": status,
                "reason": reason,
            }
        )
    return result


_PAINT = """el => {
 const b=el.getBoundingClientRect();
 let left=b.left,right=b.right,top=b.top,bottom=b.bottom,
   hidden=getComputedStyle(el).visibility!=='visible',unsupported=false;
 for(let p=el;p;p=p.parentElement){
   const c=getComputedStyle(p),r=p.getBoundingClientRect();
   const paint=/(^| )(paint|content|strict)( |$)/.test(c.contain)||c.contentVisibility==='auto';
   const noClipBox=c.display==='contents'||
     (c.display==='inline'&&p.namespaceURI==='http://www.w3.org/1999/xhtml'&&
       p.clientWidth===0&&p.clientHeight===0);
   hidden ||= c.display==='none'||(c.display!=='contents'&&Number(c.opacity)===0)||
      (p!==el&&!noClipBox&&c.contentVisibility==='hidden');
   unsupported ||= (c.display==='contents'&&Number(c.opacity)!==1)||
      c.clipPath!=='none'||c.clip!=='auto'||c.maskImage!=='none'||
      c.filter!=='none'||c.transform!=='none'||c.scale!=='none'||c.rotate!=='none'||
      c.translate!=='none'||c.perspective!=='none'||Number(c.zoom)!==1;
   if(p!==el&&!noClipBox){
     if(paint||['hidden','clip','scroll','auto'].includes(c.overflowX)){
       left=Math.max(left,r.left+Math.max(p.clientLeft,parseFloat(c.borderLeftWidth)));
       right=Math.min(right,r.right-parseFloat(c.borderRightWidth),r.left+p.clientLeft+p.clientWidth);
     }
     if(paint||['hidden','clip','scroll','auto'].includes(c.overflowY)){
       top=Math.max(top,r.top+Math.max(p.clientTop,parseFloat(c.borderTopWidth)));
       bottom=Math.min(bottom,r.bottom-parseFloat(c.borderBottomWidth),r.top+p.clientTop+p.clientHeight);
     }
   }
 }
 return {hidden,unsupported,clipped:right<=left||bottom<=top,zero:b.width<=0||b.height<=0};
}"""

_TEXT_PAINT = """(el,frame) => {
 const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);
 let seen=false,missing=false,unavailable=null,n;
 while((n=walker.nextNode())){
   if(!n.textContent.trim())continue;
   seen=true;
   const range=document.createRange(),parent=n.parentElement;
   range.selectNodeContents(n);
   let boxes=[...range.getClientRects()].filter(b=>b.width>0&&b.height>0)
     .map(b=>({left:b.left,right:b.right,top:b.top,bottom:b.bottom}));
   if(frame)boxes=boxes.map(b=>({
     left:Math.max(b.left,Number(frame.x)),top:Math.max(b.top,Number(frame.y)),
     right:Math.min(b.right,Number(frame.x)+Number(frame.width)),
     bottom:Math.min(b.bottom,Number(frame.y)+Number(frame.height))
   }));
   const style=getComputedStyle(parent);
   const transparent=colour=>{
     if(colour==='transparent')return true;
     const m=colour.match(
       /^rgba?\\(\\s*[0-9.]+,\\s*[0-9.]+,\\s*[0-9.]+(?:,\\s*([0-9.]+))?\\s*\\)$/);
     if(!m)return null;
     return m[1]!==undefined&&Number(m[1])===0;
   };
   let hidden=style.visibility!=='visible',unsupported=false;
   for(let p=parent;p;p=p.parentElement){
     const c=getComputedStyle(p),r=p.getBoundingClientRect();
     const noClipBox=c.display==='contents'||
       (c.display==='inline'&&p.namespaceURI==='http://www.w3.org/1999/xhtml'&&
         p.clientWidth===0&&p.clientHeight===0);
     hidden ||= c.display==='none'||(c.display!=='contents'&&Number(c.opacity)===0)||
        (!noClipBox&&c.contentVisibility==='hidden');
     unsupported ||= (c.display==='contents'&&Number(c.opacity)!==1)||
        c.clipPath!=='none'||c.clip!=='auto'||c.maskImage!=='none'||c.filter!=='none'||
        c.textShadow!=='none'||c.webkitTextStrokeWidth!=='0px'||
        c.backgroundClip.split(',').some(value=>value.trim()==='text')||
        c.transform!=='none'||c.scale!=='none'||c.rotate!=='none'||c.translate!=='none'||
        c.perspective!=='none'||Number(c.zoom)!==1;
     if(noClipBox)continue;
     const paint=/(^| )(paint|content|strict)( |$)/.test(c.contain)||c.contentVisibility==='auto';
     const x=paint||['hidden','clip','scroll','auto'].includes(c.overflowX);
     const y=paint||['hidden','clip','scroll','auto'].includes(c.overflowY);
     boxes=boxes.map(b=>({
       left:x?Math.max(b.left,r.left+Math.max(p.clientLeft,parseFloat(c.borderLeftWidth))):b.left,
       right:x?Math.min(b.right,r.right-parseFloat(c.borderRightWidth),
         r.left+p.clientLeft+p.clientWidth):b.right,
       top:y?Math.max(b.top,r.top+Math.max(p.clientTop,parseFloat(c.borderTopWidth))):b.top,
       bottom:y?Math.min(b.bottom,r.bottom-parseFloat(c.borderBottomWidth),
         r.top+p.clientTop+p.clientHeight):b.bottom
     }));
   }
   if(hidden){missing=true;continue;}
   if(unsupported){unavailable ||= 'unsupported APP text paint';continue;}
   if(!boxes.length||boxes.some(b=>b.right<=b.left||b.bottom<=b.top)){missing=true;continue;}
   const ink=transparent(style.webkitTextFillColor||style.color);
   if(ink===null){unavailable ||= 'unsupported APP text alpha';continue;}
   if(ink)missing=true;
 }
 if(missing)return false;
 if(unavailable)throw Error(unavailable);
 return seen;
}"""

_VALUES = """el => {
 const r=el.getBoundingClientRect(),c=getComputedStyle(el);
 return {bounds:Object.fromEntries(['x','y','width','height'].map(k=>[k,String(r[k])])),
   text:el.textContent,width:String(r.width),height:String(r.height),
   backgroundColor:c.backgroundColor,color:c.color,fontFamily:c.fontFamily,
   fontSize:c.fontSize,fontWeight:c.fontWeight,
   visible:el.checkVisibility({checkOpacity:true,checkVisibilityCSS:true})&&r.width>0&&r.height>0};
}"""


def observe_roles(page, bindings, constraints):
    text_roles = [row["element"] for row in constraints if row["property"] == "text"]
    script = (
        "({bindings,textRoles})=>{const values=("
        + _VALUES
        + ");const paint=("
        + _PAINT
        + ");const textPaint=("
        + _TEXT_PAINT
        + """);
        for(const s of bindings.document_witnesses){
          if(document.querySelectorAll(s).length!==1)
            throw Error('unconfirmed APP structural witness: '+s);
        }
        const roots=document.querySelectorAll(bindings.root);
        if(roots.length!==1)throw Error('missing/ambiguous APP root binding');
        const root=roots[0],frame=values(root).bounds,elements={};
        for(const [role,selector] of Object.entries({root:null,...bindings.elements})){
          const row={count:null};elements[role]=row;
          try{
            const nodes=selector===null?[root]:[...root.querySelectorAll(selector)];
            row.count=nodes.length;if(nodes.length!==1)continue;
            const el=nodes[0];
            if(selector!==null&&(!root.contains(el)||root===el))
              throw Error('escaping APP binding');
            const p=paint(el),raw=values(el);row.raw=raw;
            if(p.hidden){row.visible=false;row.paint=p;continue;}
            if(p.unsupported)throw Error('unsupported APP visibility paint effect');
            if(textRoles.includes(role))raw.textVisible=textPaint(el,role==='root'?null:frame);
            row.visible=raw.visible&&!p.hidden&&!p.clipped&&!p.zero;row.paint=p;
          }catch(error){row.error=String(error.message)}
        }
        return elements;
        }"""
    )
    return page.evaluate(script, {"bindings": bindings, "textRoles": text_roles})


def settle_required(page, bindings, constraints):
    require(type(constraints) is list and bool(constraints), "explicit APP inventory required")
    page.evaluate("document.fonts.ready")
    previous, streaks, history = {}, {}, []
    for sample in range(60):
        page.evaluate("()=>new Promise(requestAnimationFrame)")
        elements = observe_roles(page, bindings, constraints)
        facts = {}
        for row in constraints:
            prop = row["property"]
            require(prop in RAW_KEYS, "unsupported APP settlement property")
            node = elements[row["element"]]
            raw = node.get("raw", {})
            facts[row["id"]] = {
                "correspondence": {key: node.get(key) for key in ("count", "visible", "error")},
                "raw": True
                if prop == "presence" and node["count"] == 1
                else raw.get(RAW_KEYS[prop]),
                "text_paint": raw.get("textVisible") if prop == "text" else None,
            }
        history.append({"sample": sample + 1, "required": facts})
        for identity, signature in facts.items():
            streaks[identity] = (
                streaks.get(identity, 0) + 1 if previous.get(identity) == signature else 0
            )
        unstable = [identity for identity in facts if streaks[identity] < 3]
        if not unstable:
            break
        previous = facts
    return {
        "elements": elements,
        "sample_count": sample + 1,
        "samples": history,
        "unstable_ids": sorted(unstable),
        "error": (
            "unstable required APP observations after 60 animation frames: "
            + ", ".join(sorted(unstable))
        )
        if unstable
        else None,
    }


def acquire(browser, record, build_root, bindings, environment, output, *, constraints):
    from playwright.sync_api import Error as BrowserError

    observed = {
        "elements": {},
        "loaded_resources": [],
        "settlement": None,
        "acquisition_error": None,
        "error": None,
    }
    errors, seen, completed, replies = [], set(), set(), {}
    output = Path(output)
    with snapshot.serve(record, build_root) as (origin, routes):
        context = browser.new_context(
            viewport=environment["viewport"],
            device_scale_factor=float(environment["device_scale"]),
            color_scheme=environment["color_scheme"],
            locale=environment["locale"],
            timezone_id=environment["timezone"],
            reduced_motion=environment["reduced_motion"],
            service_workers="block",
        )
        try:
            page = context.new_page()
            page.set_default_timeout(3000)
            page.on("pageerror", lambda error: errors.append("APP page error: " + str(error)))
            page.on("download", lambda _item: errors.append("unapproved APP download"))
            context.on("page", lambda _page: errors.append("unapproved APP popup"))

            def request(route):
                path = route.request.url.removeprefix(origin)
                if (
                    route.request.url != origin + path
                    or path not in routes
                    or route.request.method != "GET"
                ):
                    errors.append("unapproved APP request: " + route.request.url)
                    route.abort()
                else:
                    route.continue_()

            def response(reply):
                path = reply.url.removeprefix(origin)
                if path not in routes or path in seen:
                    errors.append("unapproved/duplicate APP response: " + reply.url)
                    return
                seen.add(path)
                replies[path] = reply

            def read_response(path, reply):
                row, body = routes[path], reply.body()
                if (
                    reply.status != 200
                    or reply.from_service_worker
                    or reply.request.redirected_from is not None
                    or body != row["body"]
                    or reply.headers.get("content-type") != row["content_type"]
                ):
                    errors.append("APP browser-loaded response identity mismatch: " + path)
                name = "responses/" + row["path"] + ".body"
                destination = bundle.safe(output, name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("xb") as stream:
                    stream.write(body)
                observed["loaded_resources"].append(
                    {
                        "url": path,
                        "path": row["path"],
                        "hash": bundle.raw(body),
                        "status": reply.status,
                        "content_type": reply.headers.get("content-type"),
                        "artifact": name,
                        "resource_type": reply.request.resource_type,
                    }
                )

            def websocket(socket):
                errors.append("unapproved APP websocket: " + socket.url)
                socket.close()

            context.route("**/*", request)
            context.route_web_socket("**/*", websocket)
            page.on("response", response)
            page.on("requestfinished", lambda req: completed.add(req.url.removeprefix(origin)))
            page.on("requestfailed", lambda req: errors.append("APP request failed: " + req.url))
            page.goto(origin + record["configuration"]["entry"], wait_until="load", timeout=5000)
            for _ in range(100):
                if seen == set(routes) and completed == set(routes):
                    break
                page.wait_for_timeout(50)
            require(seen == set(routes), "incomplete APP response inventory")
            require(completed == set(routes), "incomplete APP response bodies")
            for path in sorted(replies):
                read_response(path, replies[path])
            page.wait_for_timeout(30)
            settled = settle_required(page, bindings, constraints)
            observed["elements"] = settled["elements"]
            observed["settlement"] = {
                key: value for key, value in settled.items() if key != "elements"
            }
            actual_environment = page.evaluate(
                "()=>({width:innerWidth,height:innerHeight,device_scale:String(devicePixelRatio)})"
            )
            require(
                actual_environment
                == {**environment["viewport"], "device_scale": environment["device_scale"]},
                "APP viewport/device-scale mismatch",
            )
            observed["environment"] = environment
            page.screenshot(path=str(output / "app.png"), full_page=True, timeout=5000)
            observed["capture_hash"] = bundle.file_hash(output / "app.png")
        except (BrowserError, ValueError, OSError) as exc:
            errors.append(str(exc))
        finally:
            try:
                context.close()
            except BrowserError as exc:
                errors.append("APP context cleanup unavailable: " + str(exc))
    observed["loaded_resources"].sort(key=lambda row: row["url"])
    observed["acquisition_error"] = "; ".join(errors) if errors else None
    settlement_error = (observed["settlement"] or {}).get("error")
    observed["error"] = (
        "; ".join(filter(None, (observed["acquisition_error"], settlement_error))) or None
    )
    return observed


PRODUCER_PINS = {
    # Clean producer cut 80f178ea1b25ebb0fff7b3e8c6651fcb4aa3e2b6.
    # Changed helper bytes require NEW source and policy approval epochs.
    "confirmed_source.py": (
        "sha256:44cf6e2dd260f592a39ea63dc6677c4e7699e358bb6e406e6264dbe488594e11"
    ),
    "capture_confirmed.py": (
        "sha256:483656876476797885742f37b142920d1341d353b0880906fac1e8700d059bcb"
    ),
    "design_input.py": "sha256:442710e8c2d4e7f218a5edd4d15f3811d8446ad74e8dc9e4e8adb25b01990009",
    "redline_intake.py": "sha256:d334fd387ef39d5ad8b60b3eb1d1173254a1504ec22b786a71d37c30dbb9438e",
    "resolve_redline.py": "sha256:4ac7206d58f7af1cab12ad71f32c373d91afd905284242e78a18e222d7219b57",
    "validate_redline.py": (
        "sha256:b98477ef04f7caa7a2fb80863f91e90e2a079971b5456b1f3ee16a6cc1f575bc"
    ),
}
HELPERS = (
    "static_contract.py",
    "static_snapshot.py",
    "evidence_io.py",
    "evidence_runtime.py",
)
NORMALIZERS = {
    "properties": APP_NORMALIZERS,
    "family": {
        "version": FAMILY_NORMALIZER,
        "generics": list(GENERICS),
        "reserved": list(RESERVED),
        "identifier": _IDENT,
        "quoted": r"[A-Za-z][A-Za-z0-9 -]*",
        "quoted_spacing": "literal",
        "unquoted_spacing": "collapse-space-tab",
        "named_case": "literal",
        "generic_case": "lowercase",
        "fallback_order": "literal",
        "escapes_nonascii_functions_quoted_commas": "refuse",
    },
    "visibility": "scoped-dom-text-ancestor-overflow-and-paint-intersection-app/3",
    "effective_visibility": "computed-at-bound-element-and-each-text-parent-not-hidden-attribute",
    "content_visibility": "own-box-retained;applicable-container-suppresses-contents-not-own-box",
    "clipping_boxes": "applicable-boxes-not-display-contents-or-boxless-HTML-inline",
    "boxless_opacity": "display-contents-nondefault-opacity-unknown-not-conclusive-hidden",
    "text_ink": "effective-fill;unsupported-shadow-stroke-text-background-clip-before-alpha",
    "absence_order": "independent-known-absence-before-unrelated-unsupported-effects",
    "raw_dom_text": "literal-including-whitespace",
    "empty_text": "literal-DOM-value-no-ghost-ink-visible-bound-box-still-required",
    "visible_text": "positive-area-per-non-whitespace-range-not-occlusion-or-legibility",
    "settlement": "complete-responses-fonts-ready-four-equal-required-fact-and-visibility-frames",
    "partial_instability": "per-required-id-last-four-atomic-samples-raw-history-retained",
}


def source_at(policy):
    require(
        all(type(pin) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", pin)
            for pin in PRODUCER_PINS.values()),
        "clean source producer cut is not sealed",
    )
    root = Path(policy["producer"])
    for name, expected in PRODUCER_PINS.items():
        require(bundle.file_hash(root / name) == expected, "source helper changed: " + name)
    sys.path.insert(0, str(root))
    try:
        producer = importlib.import_module("confirmed_source")
        for name in PRODUCER_PINS:
            module_name = name.removesuffix(".py")
            module = importlib.import_module(module_name)
            require(
                Path(module.__file__).resolve() == (root / name).resolve(),
                "foreign source helper origin: " + name,
            )
        source = policy["source"]
        require(
            type(source) is dict
            and set(source)
            == {
                "root",
                "input_hash",
                "approval_hash",
                "target_revision",
                "request_hash",
                "contract_version",
                "profile",
            },
            "unsupported source identity fields",
        )
        require(
            bundle.file_hash(Path(source["root"]) / "input.json") == source["input_hash"],
            "approved input bytes changed",
        )
        require(
            bundle.file_hash(Path(source["root"]) / "approval.json") == source["approval_hash"],
            "source approval bytes changed",
        )
        doc = producer.inspect(source["root"])
        require(
            doc["core"]["runtime"]["tooling"]
            == {name: pin.removeprefix("sha256:") for name, pin in PRODUCER_PINS.items()},
            "source tooling approval epoch differs from pinned producer",
        )
        require(
            doc["version"] == source["contract_version"] == "vellum-confirmed-source/0.2"
            and doc["profile"] == source["profile"] == "static-css-subset/1"
            and doc["target_revision"] == source["target_revision"]
            and producer.request_hash(doc["request"]) == source["request_hash"],
            "source target/request identity mismatch",
        )
        return doc, producer
    finally:
        sys.path.pop(0)


def policy_hash(policy):
    return bundle.identity(
        "servo-static-app-policy-v1",
        {key: value for key, value in policy.items() if key != "approval"},
    )


def _bindings(bindings, core):
    require(
        type(bindings) is dict and set(bindings) == {"root", "document_witnesses", "elements"},
        "unsupported APP bindings",
    )
    roles = {row["element"] for row in core["policy"]} - {"root"}
    require(
        type(bindings["elements"]) is dict and set(bindings["elements"]) == roles,
        "unconfirmed/missing/extra APP role bindings",
    )
    witnesses = bindings["document_witnesses"]
    require(
        type(witnesses) is list and bool(witnesses) and len(set(witnesses)) == len(witnesses),
        "independent structural witnesses required",
    )
    for selector in [bindings["root"], *witnesses, *bindings["elements"].values()]:
        require(
            type(selector) is str
            and bool(selector.strip())
            and ">>" not in selector
            and not re.match(r"^[A-Za-z_-]+=", selector.strip())
            and not re.search(r":(?:has-text|text|visible|nth-match)\b", selector),
            "unsupported APP CSS-only binding",
        )


def runtime_inventory(browser_root):
    from evidence_runtime import _native_dependencies, check_startup_environment
    from playwright.sync_api import sync_playwright

    roots = sorted(str(Path(root).resolve()) for root in site.getsitepackages())
    check_startup_environment(sys.prefix, roots)
    bash = shutil.which("bash")
    require(bash is not None, "declared bash runtime unavailable")
    bash = Path(bash).resolve()
    files = {Path(sys.executable).resolve(), Path(sys.prefix).resolve() / "pyvenv.cfg", bash}
    for path in Path(sys.base_prefix).rglob("*"):
        if (
            "site-packages" not in path.parts
            and "__pycache__" not in path.parts
            and path.suffix != ".pyc"
            and path.is_file()
        ):
            files.add(path.resolve())
    versions, origins = {}, {}
    for name in ("playwright", "greenlet", "pyee", "typing_extensions"):
        distribution = importlib.metadata.distribution(name)
        versions[name] = distribution.version
        origins[name] = str(Path(importlib.util.find_spec(name).origin).resolve())
        for entry in distribution.files or []:
            path = Path(distribution.locate_file(entry))
            if "__pycache__" not in path.parts and path.suffix != ".pyc" and path.is_file():
                files.add(path.resolve())
    browser_root = Path(browser_root).resolve()
    members = browser_membership(browser_root)
    files.update(path.resolve() for path in browser_root.rglob("*") if path.is_file())
    with sync_playwright() as pw:
        executable = Path(pw.chromium.executable_path).resolve()
        require(executable.is_relative_to(browser_root), "browser outside runtime closure")
        browser = pw.chromium.launch(headless=True)
        try:
            browser_version = browser.version
        finally:
            browser.close()
    native = _native_dependencies(files, [sys.executable, bash])
    return {
        "python": platform.python_version(),
        "executable": str(Path(sys.executable).resolve()),
        "prefix": str(Path(sys.prefix).resolve()),
        "os": platform.platform(),
        "bash": str(bash),
        "dependencies": versions,
        "module_origins": origins,
        "site_roots": roots,
        "native_resolutions": native,
        "browser_root": str(browser_root),
        "browser_hash": bundle.file_hash(executable),
        "browser_version": browser_version,
        "browser_members": members,
        "files": [{"path": str(path), "hash": bundle.file_hash(path)} for path in sorted(files)],
    }


def browser_membership(root):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), "missing/symlink browser runtime root")
    result, identities = [], {root: bundle._file_identity(root.lstat())}
    for path in sorted(root.rglob("*")):
        identities[path] = bundle._file_identity(path.lstat())
        row = {"path": path.relative_to(root).as_posix()}
        if path.is_symlink():
            require(
                path.exists() and path.resolve().is_relative_to(root.resolve()),
                "unsupported browser runtime symlink",
            )
            row.update(kind="symlink", target=os.readlink(path))
        elif path.is_dir():
            row["kind"] = "directory"
        else:
            require(path.is_file(), "unsupported browser runtime member")
            row["kind"] = "file"
        result.append(row)
    require(
        all(bundle._file_identity(path.lstat()) == value for path, value in identities.items()),
        "browser runtime membership raced",
    )
    return result


def validate_browser_membership(runtime):
    manifest = runtime["browser_membership"]
    require(
        bundle.file_hash(manifest["path"]) == manifest["hash"],
        "browser membership manifest changed",
    )
    require(
        browser_membership(runtime["browser_root"]) == bundle.load(manifest["path"]),
        "browser runtime membership changed",
    )


def _runtime(runtime):
    from evidence_runtime import check_startup_environment

    manifest = runtime["manifest"]
    require(bundle.file_hash(manifest["path"]) == manifest["hash"], "runtime manifest changed")
    for row in bundle.load(manifest["path"]):
        require(
            bundle.file_hash(row["path"]) == row["hash"],
            "runtime dependency changed: " + row["path"],
        )
    validate_browser_membership(runtime)
    require(
        runtime["python"] == platform.python_version()
        and runtime["executable"] == str(Path(sys.executable).resolve())
        and runtime["prefix"] == str(Path(sys.prefix).resolve())
        and runtime["os"] == platform.platform()
        and shutil.which("bash") is not None
        and str(Path(shutil.which("bash")).resolve()) == runtime["bash"]
        and os.environ.get("PLAYWRIGHT_BROWSERS_PATH") == runtime["browser_root"],
        "runtime environment changed",
    )
    require(
        sys.dont_write_bytecode and sys.pycache_prefix and not Path(sys.pycache_prefix).exists(),
        "source-only Python startup required",
    )
    require(
        not any(
            os.environ.get(name)
            for name in (
                "PYTHONPATH",
                "PYTHONHOME",
                "PYTHONSTARTUP",
                "PYTHONINSPECT",
                "BASH_ENV",
                "ENV",
            )
        ),
        "unsupported Python/shell startup environment",
    )
    roots = sorted(str(Path(root).resolve()) for root in site.getsitepackages())
    require(roots == runtime["site_roots"], "runtime startup roots changed")
    check_startup_environment(sys.prefix, roots)
    for name, version in runtime["dependencies"].items():
        require(
            importlib.metadata.version(name) == version
            and str(Path(importlib.util.find_spec(name).origin).resolve())
            == runtime["module_origins"][name],
            "runtime module changed: " + name,
        )
    for row in runtime["native_resolutions"]:
        require(
            str(Path(row["path"]).resolve()) == row["resolved"]
            and bundle.file_hash(row["resolved"]) == row["hash"],
            "native runtime resolution changed",
        )


def validated_policy(path):
    policy = bundle.load(path)
    require(
        set(policy)
        == {
            "schema_version",
            "kind",
            "version",
            "target",
            "producer",
            "source",
            "bindings",
            "normalizers",
            "constraints",
            "environment",
            "selection",
            "output_root",
            "runtime",
            "evaluator_files",
            "residuals",
            "approval",
        }
        and type(policy["schema_version"]) is int
        and policy["schema_version"] == 1
        and policy["kind"] == "static_source_contract_app_policy"
        and policy["version"] == VERSION,
        "unsupported static APP policy",
    )
    approval = policy["approval"]
    require(
        type(approval) is dict
        and approval.get("decision") == "approved"
        and approval.get("author")
        and approval.get("reviewer")
        and approval["author"] != approval["reviewer"]
        and approval.get("policy_hash") == policy_hash(policy),
        "independent exact APP policy approval missing/stale",
    )
    review = Path(path).with_name("policy-review.json")
    require(bundle.file_hash(review) == approval["review_record_hash"], "APP policy review changed")
    for row in policy["evaluator_files"]:
        require(bundle.file_hash(row["path"]) == row["hash"], "APP evaluator changed")
    helper = Path(policy["producer"]).parent
    require(
        policy["evaluator_files"]
        == [
            {"path": str(helper / row["path"]), "hash": row["hash"]}
            for row in bundle.inventory(helper)
        ],
        "APP helper inventory changed",
    )
    _runtime(policy["runtime"])
    doc, producer = source_at(policy)
    core = doc["core"]
    _bindings(policy["bindings"], core)
    require(
        canonical(policy["normalizers"]) == canonical(NORMALIZERS), "unsupported APP normalizers"
    )
    require(
        policy["constraints"]
        == [{**row, "app_normalizer": APP_NORMALIZERS[row["property"]]} for row in core["policy"]],
        "source comparison/inventory or explicit APP normalizer changed",
    )
    require(
        policy["environment"] == core["manifest"]["environment"],
        "APP environment differs from approved source",
    )
    require(
        policy["output_root"].split("/").count("{run_id}") == 1,
        "APP output needs one current run segment",
    )
    return policy, doc, producer


def current_binding(policy):
    target = Path(policy["target"])
    path = bundle.safe(target, policy["selection"])
    selection = bundle.load(path)
    require(
        type(selection) is dict and set(selection) == {"build", "delivery"},
        "unsupported static candidate selection",
    )
    build_root, delivery = (bundle.safe(target, selection[name]) for name in ("build", "delivery"))
    record = bundle.load(build_root / "build.json")
    source = Path(record["source"])
    require(
        source.is_absolute()
        and not source.is_symlink()
        and str(source.resolve()) == record["source"]
        and source.resolve().is_relative_to(target.resolve()),
        "snapshot source escapes target",
    )
    snapshot.verify(record, build_root, delivery)
    return {
        "selection": selection,
        "selection_hash": bundle.file_hash(path),
        "build": record,
        "build_root": str(build_root),
        "delivery": str(delivery),
    }


def driver_seal(policy, ids):
    target = Path(policy["target"])
    plan = bundle.load(target / "spec/oracle/static/checks.json")
    binding = plan.get("approved_required_binding", {})
    require(
        plan.get("approval_status") == "approved"
        and plan.get("required_policy") == {"schema_version": 1, "enabled": True}
        and [row["id"] for row in plan["checks"]] == ids
        and all(row.get("required") is True for row in plan["checks"])
        and binding.get("required_ids") == ids,
        "static required inventory not sealed",
    )
    pins = [row for row in binding.get("evaluator_artifacts", []) if row["path"] == "oracle.sh"]
    require(
        len(pins) == 1 and pins[0]["hash"] == bundle.file_hash(target / "oracle.sh"),
        "static oracle driver seal missing/changed",
    )


def _existing(policy, doc, binding, root, run_id):
    envelope = bundle.load(root / "evidence.json")
    invocation = Path(policy["target"]) / ".servo/gate-runs" / run_id
    claim = bundle.load(invocation / "static-acquisition-claim.json")
    receipt = bundle.load(invocation / "static-acquisition-receipt.json")
    require(
        claim == bundle.load(root / "claim.json")
        and claim["run_id"] == run_id
        and claim["policy_hash"] == policy_hash(policy)
        and claim["output_root"] == root.relative_to(Path(policy["target"])).as_posix()
        and envelope["acquisition_nonce"] == claim["nonce"]
        and receipt
        == {
            "run_id": run_id,
            "nonce": claim["nonce"],
            "envelope_hash": bundle.file_hash(root / "evidence.json"),
        },
        "foreign/replayed static acquisition",
    )
    require(
        envelope["run_id"] == run_id
        and envelope["policy"]["hash"] == policy_hash(policy)
        and envelope["policy"]["required_ids"] == doc["core"]["inventory"]
        and [row["id"] for row in envelope["constraints"]] == doc["core"]["inventory"],
        "static run/policy/inventory mismatch",
    )
    require(
        envelope["source"] == policy["source"]
        and envelope["build"] == binding["build"]
        and envelope["current_delivery"]
        == {
            "path": binding["delivery"],
            "selection_hash": binding["selection_hash"],
            "output_hash": binding["build"]["output_hash"],
        },
        "source/candidate/current delivery changed since capture",
    )
    require(
        [row for row in bundle.inventory(root) if row["path"] != "evidence.json"]
        == envelope["artifacts"],
        "static output closure changed",
    )
    return envelope


def evaluate(policy_path):
    from evidence_runtime import _run_id, _summary
    from playwright.sync_api import Error as BrowserError
    from playwright.sync_api import sync_playwright

    policy, doc, producer = validated_policy(policy_path)
    target = Path(policy["target"])
    run_id = _run_id(target)
    driver_seal(policy, doc["core"]["inventory"])
    binding = current_binding(policy)
    root = bundle.safe(target, policy["output_root"].replace("{run_id}", run_id))
    if root.exists():
        return _existing(policy, doc, binding, root, run_id)
    root.mkdir(parents=True)
    invocation = target / ".servo/gate-runs" / run_id
    claim = {
        "run_id": run_id,
        "nonce": secrets.token_hex(32),
        "policy_hash": policy_hash(policy),
        "output_root": root.relative_to(target).as_posix(),
    }
    bundle.publish(invocation / "static-acquisition-claim.json", claim)
    bundle.publish(root / "claim.json", claim)
    observed = {"elements": {}, "loaded_resources": [], "error": None}
    try:
        with sync_playwright() as pw:
            require(
                bundle.file_hash(pw.chromium.executable_path) == policy["runtime"]["browser_hash"],
                "browser executable changed",
            )
            browser = pw.chromium.launch(headless=True)
            try:
                require(
                    browser.version == policy["runtime"]["browser_version"],
                    "browser version changed",
                )
                observed = acquire(
                    browser,
                    binding["build"],
                    binding["build_root"],
                    policy["bindings"],
                    policy["environment"],
                    root,
                    constraints=policy["constraints"],
                )
            finally:
                browser.close()
    except BrowserError as exc:
        message = "APP browser acquisition unavailable: " + str(exc)
        observed["acquisition_error"] = "; ".join(
            filter(None, (observed.get("acquisition_error"), message))
        )
        observed["error"] = "; ".join(filter(None, (observed.get("error"), message)))
    observed.update(run_id=run_id, acquisition_nonce=claim["nonce"])
    bundle.publish(root / "observations.json", observed)
    rows = compare(doc["core"], observed, producer)
    try:
        require(
            current_binding(policy) == binding, "candidate/current delivery changed during capture"
        )
        require(validated_policy(policy_path)[0] == policy, "APP policy changed during capture")
    except (ValueError, OSError) as exc:
        rows = [
            row if row["status"] == "fail" else {**row, "status": "unknown", "reason": str(exc)}
            for row in rows
        ]
    summary = _summary(rows)
    envelope = {
        "schema_version": 1,
        "kind": "static_source_contract_evidence",
        "version": VERSION,
        "run_id": run_id,
        "acquisition_nonce": claim["nonce"],
        "source": policy["source"],
        "policy": {"hash": policy_hash(policy), "required_ids": doc["core"]["inventory"]},
        "evaluator": policy["evaluator_files"],
        "runtime": policy["runtime"],
        "build": binding["build"],
        "current_delivery": {
            "path": binding["delivery"],
            "selection_hash": binding["selection_hash"],
            "output_hash": binding["build"]["output_hash"],
        },
        "observations": {
            "path": "observations.json",
            "hash": bundle.file_hash(root / "observations.json"),
        },
        "constraints": rows,
        "summary": summary,
        "measurement_diagnostic": {
            "passed": len(summary["passed"]),
            "total": len(rows),
            "claim": "static-measurement-only-not-visual-quality",
        },
        "residuals": policy["residuals"],
        "artifacts": bundle.inventory(root),
    }
    bundle.publish(root / "evidence.json", envelope)
    bundle.publish(
        invocation / "static-acquisition-receipt.json",
        {
            "run_id": run_id,
            "nonce": claim["nonce"],
            "envelope_hash": bundle.file_hash(root / "evidence.json"),
        },
    )
    return envelope


def validate_current(policy_path, envelope_path):
    import uuid

    policy, doc, _producer = validated_policy(policy_path)
    envelope_path = Path(envelope_path)
    envelope = bundle.load(envelope_path)
    run_id = envelope["run_id"]
    require(str(uuid.UUID(run_id)) == run_id, "invalid preserved static run")
    root = bundle.safe(Path(policy["target"]), policy["output_root"].replace("{run_id}", run_id))
    require(
        envelope_path.resolve() == (root / "evidence.json").resolve(),
        "foreign static output destination",
    )
    driver_seal(policy, doc["core"]["inventory"])
    return _existing(policy, doc, current_binding(policy), root, run_id)


def prepare(target, package, producer_root, bindings_path, browser_root):
    require(
        all(type(pin) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", pin)
            for pin in PRODUCER_PINS.values()),
        "clean source producer cut is not sealed",
    )
    target = Path(target).resolve()
    require((target / "oracle.sh").is_file(), "scaffold ordinary target first")
    out = bundle.safe(target, "spec/oracle/static")
    helper = bundle.safe(target, "tools/static")
    approved = bundle.safe(target, "design-input")
    source_spec = bundle.safe(target, "spec/static.md")
    for destination in (out, helper, approved, source_spec):
        require(
            not destination.exists(),
            "preparation destination already exists: " + str(destination),
        )
        for parent in destination.parents:
            if parent == target:
                break
            require(
                not parent.exists() or parent.is_dir(),
                "preparation parent is not a directory: " + str(parent),
            )
    producer_bytes = {}
    for name, expected in PRODUCER_PINS.items():
        producer_bytes[name] = bundle.read_bytes(Path(producer_root) / name)
        require(
            bundle.raw(producer_bytes[name]) == expected,
            "preparation producer changed: " + name,
        )
    sys.path.insert(0, str(Path(producer_root)))
    try:
        producer = importlib.import_module("confirmed_source")
        doc = producer.inspect(package)
        require(
            doc["core"]["runtime"]["tooling"]
            == {name: pin.removeprefix("sha256:") for name, pin in PRODUCER_PINS.items()},
            "source tooling approval epoch differs from pinned producer",
        )
    finally:
        sys.path.pop(0)
    bindings = bundle.load(bindings_path)
    _bindings(bindings, doc["core"])
    runtime = runtime_inventory(browser_root)
    helper_bytes = {
        name: bundle.read_bytes(Path(__file__).parent / name) for name in HELPERS
    }
    out.mkdir(parents=True)
    helper.mkdir(parents=True)
    source_helper = helper / "producer"
    source_helper.mkdir()
    for directory, files in ((helper, helper_bytes), (source_helper, producer_bytes)):
        for name, data in files.items():
            with (directory / name).open("xb") as stream:
                stream.write(data)
    shutil.copytree(package, approved)
    require(producer.inspect(approved) == doc, "approved source changed during preparation")
    bundle.publish(helper / "runtime-files.json", runtime.pop("files"))
    bundle.publish(helper / "browser-membership.json", runtime.pop("browser_members"))
    runtime["browser_membership"] = {
        "path": str(helper / "browser-membership.json"),
        "hash": bundle.file_hash(helper / "browser-membership.json"),
    }
    runtime["manifest"] = {
        "path": str(helper / "runtime-files.json"),
        "hash": bundle.file_hash(helper / "runtime-files.json"),
    }
    policy = {
        "schema_version": 1,
        "kind": "static_source_contract_app_policy",
        "version": VERSION,
        "target": str(target),
        "producer": str(source_helper),
        "source": {
            "root": str(approved),
            "input_hash": bundle.file_hash(approved / "input.json"),
            "approval_hash": bundle.file_hash(approved / "approval.json"),
            "target_revision": doc["target_revision"],
            "request_hash": producer.request_hash(doc["request"]),
            "contract_version": doc["version"],
            "profile": doc["profile"],
        },
        "bindings": bindings,
        "normalizers": NORMALIZERS,
        "constraints": [
            {**row, "app_normalizer": APP_NORMALIZERS[row["property"]]}
            for row in doc["core"]["policy"]
        ],
        "environment": doc["core"]["manifest"]["environment"],
        "selection": "candidate-selection.json",
        "output_root": "spec/oracle/static/runs/{run_id}/observed",
        "runtime": runtime,
        "evaluator_files": [
            {"path": str(helper / row["path"]), "hash": row["hash"]}
            for row in bundle.inventory(helper)
        ],
        "residuals": [
            *doc["core"]["manifest"]["coverage"]["residuals"],
            (
                "Nondefault opacity on display:contents is unsupported; "
                "affected required IDs stay UNKNOWN and veto"
            ),
            "Static snapshot only; backend authenticity/full data identity unproved",
            "No whole-view/pixel/actual-face/interaction quality or full-app completion",
            "Source contract evidence is not a lifecycle completion attestation",
        ],
        "approval": {"decision": "pending"},
    }
    policy_path = out / "app-policy.json"
    with source_spec.open("x", encoding="utf-8") as stream:
        stream.write(
            "# Explicit static source contract only\n\n"
            "No whole-app, pixel, actual-face, backend or lifecycle completion claim.\n\n"
            + "\n".join("- Required: " + identity for identity in doc["core"]["inventory"])
            + "\n"
        )
    bundle.publish(policy_path, policy)
    artifacts = [
        p.relative_to(target).as_posix()
        for root in (helper, approved)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    ]
    artifacts += ["spec/oracle/static/app-policy.json"]
    bundle.publish(
        out / "checks.json",
        {
            "schema_version": 1,
            "spec_id": "static",
            "source_spec_path": "spec/static.md",
            "source_hash": bundle.file_hash(source_spec),
            "required_policy": {"schema_version": 1, "enabled": True},
            "checks": [
                {
                    "id": identity,
                    "family": "command",
                    "required": True,
                    "timeout": 180,
                    "command": [
                        str(Path(sys.prefix) / "bin/python3"),
                        "-I",
                        "-B",
                        str(helper / "static_contract.py"),
                        "evaluate",
                        "--policy",
                        str(policy_path),
                        "--constraint",
                        identity,
                    ],
                    "evaluator_artifacts": artifacts,
                    "refusal_exit_codes": [2],
                    "result_artifact": {
                        "root": policy["output_root"],
                        "manifest": "evidence.json",
                        "schema_version": 1,
                        "kind": "static_source_contract_evidence",
                    },
                }
                for identity in doc["core"]["inventory"]
            ],
            "residual_judgment": [],
        },
    )
    return policy_path


def approve_policy(path, review_path):
    path = Path(path)
    policy, review = bundle.load(path), bundle.load(review_path)
    require(policy["approval"] == {"decision": "pending"}, "APP policy already approved")
    require(
        review.get("verdict") == "pass"
        and review.get("author")
        and review.get("reviewer")
        and review["author"] != review["reviewer"]
        and review.get("policy_hash") == policy_hash(policy),
        "independent exact APP policy/pre-result review required",
    )
    destination = path.with_name("policy-review.json")
    require(not destination.exists(), "APP policy review already exists")
    shutil.copyfile(review_path, destination)
    policy["approval"] = {
        "decision": "approved",
        "author": review["author"],
        "reviewer": review["reviewer"],
        "policy_hash": policy_hash(policy),
        "review_record_hash": bundle.file_hash(destination),
    }
    path.write_bytes(canonical(policy) + b"\n")
    checks_path = path.with_name("checks.json")
    checks = bundle.load(checks_path)
    for check in checks["checks"]:
        check["evaluator_artifacts"].append(
            destination.relative_to(Path(policy["target"])).as_posix()
        )
    checks_path.write_bytes(canonical(checks) + b"\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "approve", "evaluate", "verify-current"))
    for name in (
        "policy",
        "envelope",
        "review",
        "target",
        "package",
        "producer-root",
        "bindings",
        "browser-root",
    ):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--constraint")
    args = parser.parse_args(argv)
    try:
        if args.operation == "prepare":
            require(
                all(
                    (
                        args.target,
                        args.package,
                        args.producer_root,
                        args.bindings,
                        args.browser_root,
                    )
                ),
                "all preparation paths required",
            )
            path = prepare(
                args.target, args.package, args.producer_root, args.bindings, args.browser_root
            )
            print(
                canonical(
                    {
                        "policy": str(path),
                        "policy_hash": policy_hash(bundle.load(path)),
                        "status": "pending-independent-review-not-installed",
                    }
                ).decode()
            )
            return 0
        require(args.policy is not None, "APP policy path required")
        if args.operation == "approve":
            require(args.review is not None, "independent review required")
            approve_policy(args.policy, args.review)
            return 0
        if args.operation == "verify-current":
            require(args.envelope is not None, "preserved static envelope required")
            envelope = validate_current(args.policy, args.envelope)
            print(
                canonical(
                    {
                        "preserved_summary": envelope["summary"],
                        "claim": "byte-identity-readback-only-no-capture-or-rescore",
                    }
                ).decode()
            )
            return 0
        envelope = evaluate(args.policy)
        matches = [row for row in envelope["constraints"] if row["id"] == args.constraint]
        require(len(matches) == 1, "unknown static required constraint")
        print(canonical(matches[0]).decode())
        return {"pass": 0, "fail": 1, "unknown": 2}[matches[0]["status"]]
    except (ValueError, OSError, KeyError, TypeError, ImportError, RuntimeError) as exc:
        print("REFUSE static APP evidence: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
