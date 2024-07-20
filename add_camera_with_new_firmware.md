### Option 1 - Block Internet access

1. Block internet access to this device on your router.
2. Make a factory reset, pressing 5 seconds on the reset button.
3. Remove the camera from tapo app, and add it again.
4. When asks to reset it completely, do it, and configure the camera again.
5. Create the account credentials for your camera.
6. Configure it in home assistant and done.

Discovered & Documented by [@vitorsemeano](https://github.com/vitorsemeano).

### Option 2 - Block DNS (via pihole for example)

1. Block DNS resolution for domains `n-device-api.tplinkcloud.com` and `security.iot.i.tplinknbu.com`
2. Make a factory reset, pressing 5 seconds on the reset button.
3. Remove the camera from tapo app, and add it again.
4. When asks to reset it completely, do it, and configure the camera again.
5. Create the account credentials for your camera.
6. Configure it in home assistant and done.

Discovered & Documented by [@lorenzomoriconi](https://github.com/lorenzomoriconi).

### Option 3 - Downgrade camera firmware

Follow https://github.com/JurajNyiri/HomeAssistant-Tapo-Control/discussions/625#discussion-6941269.

### Something not working right or have something to share?

Ask a [question](https://github.com/JurajNyiri/HomeAssistant-Tapo-Control/discussions/categories/q-a) or [discuss](https://github.com/JurajNyiri/HomeAssistant-Tapo-Control/discussions/categories/discuss).
