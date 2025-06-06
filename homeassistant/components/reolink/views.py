"""Reolink Integration views."""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from http import HTTPStatus
import logging

from aiohttp import ClientError, ClientTimeout, web
from reolink_aio.enums import VodRequestType
from reolink_aio.exceptions import ReolinkError

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_source import Unresolvable
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.ssl import SSLCipherList

from .util import get_host

_LOGGER = logging.getLogger(__name__)


@callback
def async_generate_playback_proxy_url(
    config_entry_id: str, channel: int, filename: str, stream_res: str, vod_type: str
) -> str:
    """Generate proxy URL for event video."""

    url_format = PlaybackProxyView.url
    return url_format.format(
        config_entry_id=config_entry_id,
        channel=channel,
        filename=urlsafe_b64encode(filename.encode("utf-8")).decode("utf-8"),
        stream_res=stream_res,
        vod_type=vod_type,
    )


class PlaybackProxyView(HomeAssistantView):
    """View to proxy playback video from Reolink."""

    requires_auth = True
    url = "/api/reolink/video/{config_entry_id}/{channel}/{stream_res}/{vod_type}/{filename}"
    name = "api:reolink_playback"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a proxy view."""
        self.hass = hass
        self.session = async_get_clientsession(
            hass,
            verify_ssl=False,
            ssl_cipher=SSLCipherList.INSECURE,
        )
        self._vod_type: str | None = None

    async def get(
        self,
        request: web.Request,
        config_entry_id: str,
        channel: str,
        stream_res: str,
        vod_type: str,
        filename: str,
        retry: int = 2,
    ) -> web.StreamResponse:
        """Get playback proxy video response."""
        retry = retry - 1

        filename_decoded = urlsafe_b64decode(filename.encode("utf-8")).decode("utf-8")
        ch = int(channel)
        if self._vod_type is not None:
            vod_type = self._vod_type
        try:
            host = get_host(self.hass, config_entry_id)
        except Unresolvable:
            err_str = f"Reolink playback proxy could not find config entry id: {config_entry_id}"
            _LOGGER.warning(err_str)
            return web.Response(body=err_str, status=HTTPStatus.BAD_REQUEST)

        try:
            mime_type, reolink_url = await host.api.get_vod_source(
                ch, filename_decoded, stream_res, VodRequestType(vod_type)
            )
        except ReolinkError as err:
            _LOGGER.warning("Reolink playback proxy error: %s", str(err))
            return web.Response(body=str(err), status=HTTPStatus.BAD_REQUEST)

        headers = dict(request.headers)
        headers.pop("Host", None)
        headers.pop("Referer", None)

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Requested Playback Proxy Method %s, Headers: %s",
                request.method,
                headers,
            )
            _LOGGER.debug(
                "Opening VOD stream from %s: %s",
                host.api.camera_name(ch),
                host.api.hide_password(reolink_url),
            )

        try:
            reolink_response = await self.session.get(
                reolink_url,
                headers=headers,
                timeout=ClientTimeout(
                    connect=15, sock_connect=15, sock_read=5, total=None
                ),
            )
        except ClientError as err:
            err_str = host.api.hide_password(
                f"Reolink playback error while getting mp4: {err!s}"
            )
            if retry <= 0:
                _LOGGER.warning(err_str)
                return web.Response(body=err_str, status=HTTPStatus.BAD_REQUEST)
            _LOGGER.debug("%s, renewing token", err_str)
            await host.api.expire_session(unsubscribe=False)
            return await self.get(
                request, config_entry_id, channel, stream_res, vod_type, filename, retry
            )

        # Reolink typo "apolication/octet-stream" instead of "application/octet-stream"
        if reolink_response.content_type not in [
            "video/mp4",
            "application/octet-stream",
            "apolication/octet-stream",
        ]:
            err_str = f"Reolink playback expected video/mp4 but got {reolink_response.content_type}"
            if (
                reolink_response.content_type == "video/x-flv"
                and vod_type == VodRequestType.PLAYBACK.value
            ):
                # next time use DOWNLOAD immediately
                self._vod_type = VodRequestType.DOWNLOAD.value
                _LOGGER.debug(
                    "%s, retrying using download instead of playback cmd", err_str
                )
                return await self.get(
                    request,
                    config_entry_id,
                    channel,
                    stream_res,
                    self._vod_type,
                    filename,
                    retry,
                )

            _LOGGER.error(err_str)
            if reolink_response.content_type == "text/html":
                text = await reolink_response.text()
                _LOGGER.debug(text)
            return web.Response(body=err_str, status=HTTPStatus.BAD_REQUEST)

        response_headers = dict(reolink_response.headers)
        _LOGGER.debug(
            "Response Playback Proxy Status %s:%s, Headers: %s",
            reolink_response.status,
            reolink_response.reason,
            response_headers,
        )
        if "Content-Type" not in response_headers:
            response_headers["Content-Type"] = reolink_response.content_type
        if response_headers["Content-Type"] == "apolication/octet-stream":
            response_headers["Content-Type"] = "application/octet-stream"

        response = web.StreamResponse(
            status=reolink_response.status,
            reason=reolink_response.reason,
            headers=response_headers,
        )

        await response.prepare(request)

        try:
            async for chunk in reolink_response.content.iter_chunked(65536):
                await response.write(chunk)
        except TimeoutError:
            _LOGGER.debug(
                "Timeout while reading Reolink playback from %s, writing EOF",
                host.api.nvr_name,
            )
        finally:
            reolink_response.release()

        await response.write_eof()
        return response
