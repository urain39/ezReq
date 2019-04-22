# Copyright (C) 2019 urain39 <urain39@qq.com>

import re
from functools import wraps
from requests import Session
from requests.adapters import HTTPAdapter

try:
  from urllib.parse import urljoin
except ImportError:
  from urlparse import urljoin

__all__ = ["EzReqError", "EzReq"]

# pylint: disable=line-too-long
_RE_NORMAL_URL = re.compile(r"^(?P<base_url>(?P<protocol>(?:ht|f)tps?\:)\/\/(?:[0-9A-Za-z][0-9A-Za-z_-]*\.)+(?:[A-Za-z]{2,}))(?:\/[0-9A-Za-z#%&./=?@_-]*)?$")

class EzReqError(Exception):
  pass


# pylint: disable=invalid-name
def normalize_url(fn):
  """
  @param fn: function
  A decorator of request method,
  which will normalize the url. like
  '/?page=rss' -> "http://example.com/?page=rss"
  """
  @wraps(fn)
  def wrapped_fn(self, url, **kwargs):
    matched = _RE_NORMAL_URL.match(url)

    if matched:
      self._base_url = matched.group("base_url")  # pylint: pylint: disable=protected-access
      self._protocol = matched.group("protocol")  # pylint: disable=protected-access

      if fn.__name__ == "__init__":
        self._last_url = url  # pylint: disable=protected-access
        return fn(self, url, **kwargs)

    # Use getattr is safe for Class.__init__
    elif getattr(self, "_initiated", False): # pylint: disable=protected-access
      if url.startswith(r"//"):
        # "//example.com"
        url = urljoin(self._protocol, url)   # pylint: disable=protected-access
        self._base_url = url  # pylint: disable=protected-access
      elif url.startswith(r"?"):
        # "?page=rss"
        url = "/" + url  # -> "/?page=rss"
        url = urljoin(self._base_url, url)   # pylint: disable=protected-access
      else:
        # "/?page=rss" "page=rss"
        url = urljoin(self._base_url, url)   # pylint: disable=protected-access
    else:
      # Only happen in Class.__init__
      #
      # Reason(s):
      #   - Use "//example.com" in Class.__init__
      #   - Use "/?page=rss" in Class.__init__
      #   - Use Unsupported URI. Like "sftp://example.com"
      raise EzReqError("Unsupported URI!")

    # pylint: disable=protected-access
    matched = _RE_NORMAL_URL.match(self._last_url)

    # pylint: disable=protected-access
    self._headers.update({
      # HTTP/2 Headers lowercase only
      "origin": matched.group("base_url"),
      "referer": self._last_url
    })

    self._last_url = url  # pylint: disable=protected-access
    return fn(self, url, **kwargs)

  return wrapped_fn


class EzReq(object):  # pylint: disable=useless-object-inheritance
  @normalize_url
  def __init__(self, base_url, **kwargs):
    self._base_url = base_url
    self._session = Session()
    self._last_url = base_url
    self._initiated = True

    # `self._headers` -> `self._session.headers`
    self._headers = self._session.headers

    headers = kwargs.pop("headers", {})
    self._session.headers.update(headers)

    max_retries = kwargs.pop("max_retries", 3)
    self._session.mount("http://", HTTPAdapter(max_retries=max_retries))
    self._session.mount("https://", HTTPAdapter(max_retries=max_retries))

  def __enter__(self):
    return self

  def __exit__(self, *args, **kwargs):
    pass

  @normalize_url
  def get(self, url, **kwargs):
    self._headers.pop("origin")
    return self._session.get(url, **kwargs)

  @normalize_url
  def post(self, url, **kwargs):
    self._headers.pop("referer")
    return self._session.post(url, **kwargs)

  @normalize_url
  def visit(self, url, **kwargs):
    """ visit a url without `referer` and `origin`.
    """
    self._headers.pop("origin")
    self._headers.pop("referer")
    return self._session.get(url, **kwargs)

  @property
  def session(self):
    return self._session
