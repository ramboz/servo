"""Actual DOM/style/state acquisition over one sealed loopback HTML response."""

import http.server
import threading
from contextlib import contextmanager
from pathlib import Path

from card_bundle import file_hash, raw, require


@contextmanager
def serve(entry):
    body = Path(entry).read_bytes()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/index.html":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/index.html", body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        require(not thread.is_alive(), "loopback server did not close")


_SNAPSHOT = """el => {
 const r=el.getBoundingClientRect(), c=getComputedStyle(el);
 function alpha(value){
   const colour=value.trim().toLowerCase();
   if(colour==='transparent')return 0;
   let token;
   if(colour.includes('/'))token=colour.slice(colour.lastIndexOf('/')+1,-1).trim();
   else if(colour.startsWith('rgba('))token=colour.slice(5,-1).split(',').pop().trim();
   else if(['rgb(','hsl(','hwb(','lab(','lch(','oklab(','oklch(','color(']
           .some(prefix=>colour.startsWith(prefix)))return 1;
   else throw Error('unsupported descendant text colour: '+value);
   const number=Number(token.endsWith('%')?token.slice(0,-1):token);
   if(!Number.isFinite(number))throw Error('unsupported descendant alpha: '+value);
   return token.endsWith('%')?number/100:number;
 }
 const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);
 let textVisible=true,seen=false,n;
 while((n=walker.nextNode())){
   if(!n.textContent.length)continue;
   seen=true;
   const p=n.parentElement,range=document.createRange(),s=getComputedStyle(p);
   range.selectNodeContents(n);
   const hasInk=[...range.getClientRects()].some(b=>b.width>0&&b.height>0);
   const transparent=alpha(s.color)===0||alpha(s.webkitTextFillColor||s.color)===0;
   let box=p;
   while(box&&getComputedStyle(box).display==='contents')box=box.parentElement;
   const visibleBox=box&&box.checkVisibility({checkOpacity:true,checkVisibilityCSS:true});
   textVisible=textVisible&&hasInk&&!transparent&&visibleBox&&
      s.visibility==='visible'&&Number(s.opacity)>0&&s.contentVisibility!=='hidden';
 }
 return {bounds:Object.fromEntries(['x','y','width','height'].map(k=>[k,String(r[k])])),
 text:el.textContent, width:String(r.width), height:String(r.height),
 backgroundColor:c.backgroundColor, color:c.color, fontFamily:c.fontFamily,
 fontSize:c.fontSize,fontWeight:c.fontWeight,textVisible:seen&&textVisible,
 visible:el.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}) &&
         r.width>0 && r.height>0};
}"""


def _one(locator, description):
    require(locator.count() == 1, "missing/ambiguous binding: " + description)
    return locator


def _settle(page, root):
    page.evaluate("document.fonts.ready")
    previous, stable = None, 0
    for _ in range(60):
        page.evaluate("() => new Promise(requestAnimationFrame)")
        current = root.evaluate("""el => [el,...el.querySelectorAll('*')].map(n=>{
          const r=n.getBoundingClientRect(),c=getComputedStyle(n);
          return [n.textContent,r.x,r.y,r.width,r.height,c.fontFamily,c.fontSize,
                  c.fontWeight,c.color,c.backgroundColor,c.display,c.visibility,c.opacity];
        })""")
        stable = stable + 1 if previous == current else 0
        if stable >= 3:
            return
        previous = current
    raise ValueError("unstable layout after 60 animation frames")


def acquire(browser, entry, mapping, state, png):
    from playwright.sync_api import Error as BrowserError

    require(state in ("normal", "open"), "unsupported state")
    result = {
        "state": state,
        "elements": {},
        "root": None,
        "driver": None,
        "loaded_resources": [],
        "state_error": None,
        "acquisition_error": None,
    }
    errors = []
    with serve(entry) as (url, sealed_bytes):
        context = browser.new_context(
            viewport={"width": 800, "height": 600}, device_scale_factor=1, service_workers="block"
        )
        try:
            page = context.new_page()
            page.set_default_timeout(3000)
            page.on("pageerror", lambda exc: errors.append("page error: " + str(exc)))
            page.on("download", lambda item: errors.append("unsupported download"))

            def request(route):
                if route.request.url != url or route.request.method != "GET":
                    errors.append("unapproved resource: " + route.request.url)
                    route.abort()
                else:
                    route.continue_()

            def websocket(socket):
                errors.append("unapproved websocket: " + socket.url)
                socket.close()

            def response(reply):
                if reply.url != url or reply.status != 200:
                    errors.append("unapproved response: " + reply.url)
                    return
                body = reply.body()
                if body != sealed_bytes or reply.from_service_worker:
                    errors.append("browser-loaded bytes differ from sealed output")
                result["loaded_resources"].append(
                    {
                        "path": "index.html",
                        "hash": raw(body),
                        "status": reply.status,
                        "resource_type": reply.request.resource_type,
                    }
                )

            context.route("**/*", request)
            context.route_web_socket("**/*", websocket)
            page.on("response", response)
            page.goto(url, wait_until="load", timeout=5000)
            root = _one(page.locator(mapping["root"]), "card root")
            driver = _one(
                _one(page.locator(mapping["driver"]["scope"]), "driver scope").locator(
                    mapping["driver"]["selector"]
                ),
                "state driver",
            )
            outside = driver.evaluate(
                "(el, selector)=>!document.querySelector(selector).contains(el)", mapping["root"]
            )
            require(outside, "state driver overlaps approved crop")
            initial = root.locator(mapping["elements"]["subtitle"])
            initial_text = initial.text_content() if initial.count() == 1 else None
            if state == "open":
                driver.click(timeout=3000)
                if initial_text != "hiking route planner":
                    result["state_error"] = "wrong initial state before completed open action"
            _settle(page, root)
            root_raw = root.evaluate(_SNAPSHOT)
            result["root"] = {"selector": mapping["root"], "bounds": root_raw["bounds"]}
            result["driver"] = {
                "scope": mapping["driver"]["scope"],
                "selector": mapping["driver"]["selector"],
                "action": "click" if state == "open" else "none",
                "completed": True,
                "initial_subtitle": initial_text,
                "outside_crop": outside,
            }
            for name, selector in mapping["elements"].items():
                locator = root.locator(selector)
                count = locator.count()
                element = {"selector": selector, "count": count, "visible": False}
                if count == 1:
                    values = locator.evaluate(_SNAPSHOT)
                    visible = values.pop("visible") and (name == "band" or values["textVisible"])
                    element.update(visible=visible, raw=values)
                result["elements"][name] = element
            if state == "open":
                subtitle = result["elements"].get("subtitle", {})
                if subtitle.get("count") == 1 and subtitle["raw"]["text"] != "opened":
                    result["state_error"] = "completed open action did not produce opened subtitle"
            viewport = page.evaluate("""()=>({width:innerWidth,height:innerHeight,
                                      device_scale:String(devicePixelRatio)})""")
            require(
                viewport == {"width": 800, "height": 600, "device_scale": "1"},
                "unexpected viewport",
            )
            result["viewport"] = viewport
            root.screenshot(path=str(png), animations="disabled", timeout=5000)
            require(
                file_hash(entry) == raw(sealed_bytes), "sealed output changed during acquisition"
            )
            require(len(context.pages) == 1, "unsupported additional app page")
            require(
                result["loaded_resources"]
                == [
                    {
                        "path": "index.html",
                        "hash": raw(sealed_bytes),
                        "status": 200,
                        "resource_type": "document",
                    }
                ],
                "incomplete browser-loaded response closure",
            )
        except (BrowserError, OSError, ValueError) as exc:
            errors.append(str(exc))
        finally:
            context.close()
    if errors:
        result["acquisition_error"] = "; ".join(errors)
    return result
