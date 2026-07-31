"""Fast, conservative bibliographic verification.

External catalogues are evidence, not authority over a photographed title page.
Exact ISBN results may complete missing fields.  A title search is accepted only
when two independent sources agree on the same title and author.
"""
import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher


FIELDS = ("title", "subtitle", "author", "publisher", "publication_place",
          "publication_year", "pages", "edition", "dimensions")


def _json(url, timeout=8):
    request = urllib.request.Request(url, headers={"User-Agent": "AICC/7.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _year(value):
    match = re.search(r"\b(18\d{2}|19\d{2}|20\d{2}|21\d{2})\b", str(value or ""))
    return match.group(1) if match else ""


def _isbn(value):
    return re.sub(r"[^0-9Xx]", "", str(value or "")).upper()


def _norm(value):
    value = str(value or "").lower()
    value = (value.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
             .replace("ى", "ي").replace("ة", "ه"))
    return re.sub(r"[\W_]+", "", value)


def _has_arabic(value):
    return bool(re.search(r"[\u0600-\u06ff]", str(value or "")))


def _similar(left, right):
    a, b = _norm(left), _norm(right)
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def _openlibrary_isbn(isbn):
    data = _json(f"https://openlibrary.org/isbn/{urllib.parse.quote(isbn)}.json")
    result = {
        "title": data.get("title", ""), "subtitle": data.get("subtitle", ""),
        "publisher": (data.get("publishers") or [""])[0],
        "publication_place": (data.get("publish_places") or [""])[0],
        "publication_year": _year(data.get("publish_date")),
        "pages": str(data.get("number_of_pages") or ""),
        "subjects": [x.get("name", "") if isinstance(x, dict) else str(x)
                     for x in (data.get("subjects") or [])],
        "ddc": (data.get("dewey_decimal_class") or [""])[0],
        "lcc": (data.get("lc_classifications") or [""])[0],
        "source": "Open Library", "matched_isbn": isbn, "match_method": "exact_isbn",
    }
    authors = []
    for author in data.get("authors") or []:
        key = author.get("key", "") if isinstance(author, dict) else ""
        if key:
            try:
                authors.append(_json(f"https://openlibrary.org{key}.json", 5).get("name", ""))
            except Exception:
                pass
    result["author"] = "، ".join(x for x in authors if x)
    return result


def _google_item(info, source="Google Books"):
    identifiers = {_isbn(x.get("identifier")) for x in info.get("industryIdentifiers") or []}
    return {
        "title": info.get("title", ""), "subtitle": info.get("subtitle", ""),
        "author": "، ".join(info.get("authors") or []),
        "publisher": info.get("publisher", ""),
        "publication_year": _year(info.get("publishedDate")),
        "pages": str(info.get("pageCount") or ""),
        "subjects": info.get("categories") or [], "source": source,
        "identifiers": sorted(x for x in identifiers if x),
    }


def _google_books_isbn(isbn):
    query = urllib.parse.urlencode({"q": f"isbn:{isbn}", "maxResults": 5})
    data = _json(f"https://www.googleapis.com/books/v1/volumes?{query}")
    wanted = _isbn(isbn)
    for item in data.get("items") or []:
        result = _google_item(item.get("volumeInfo") or {})
        if wanted in result.pop("identifiers", []):
            result.update({"matched_isbn": isbn, "match_method": "exact_isbn"})
            return result
    return {}


def _openlibrary_search(title, author):
    params = {"title": title, "limit": 5}
    if author:
        params["author"] = author
    data = _json("https://openlibrary.org/search.json?" + urllib.parse.urlencode(params))
    results = []
    for doc in data.get("docs") or []:
        results.append({
            "title": doc.get("title", ""), "author": "، ".join(doc.get("author_name") or []),
            "publisher": (doc.get("publisher") or [""])[0],
            "publication_year": str(doc.get("first_publish_year") or ""),
            "subjects": (doc.get("subject") or [])[:12],
            "source": "Open Library", "match_method": "title_author",
        })
    return results


def _google_books_search(title, author):
    query = f'intitle:"{title}"' + (f' inauthor:"{author}"' if author else "")
    params = urllib.parse.urlencode({"q": query, "maxResults": 5})
    data = _json(f"https://www.googleapis.com/books/v1/volumes?{params}")
    results = []
    for item in data.get("items") or []:
        result = _google_item(item.get("volumeInfo") or {})
        result.pop("identifiers", None)
        result["match_method"] = "title_author"
        results.append(result)
    return results


def _best_candidate(candidates, book):
    title, author = book.get("title", ""), book.get("author", "")
    ranked = []
    for item in candidates:
        title_score = _similar(title, item.get("title"))
        author_score = _similar(author, item.get("author")) if author else 0
        # A title-only hit is never enough to identify a book.
        if title_score >= .92 and author and author_score >= .82:
            ranked.append((title_score * .65 + author_score * .35, item))
    return max(ranked, default=(0, {}), key=lambda x: x[0])


def _aggregate(results, method):
    valid = [r for r in results if r and r.get("title")]
    if not valid:
        return {}
    aggregate = {"sources": [r["source"] for r in valid], "match_method": method,
                 "match_status": "exact" if method == "exact_isbn" else "strong_consensus",
                 "match_score": 100 if method == "exact_isbn" else
                                round(min(r.get("candidate_score", 0) for r in valid) * 100)}
    for field in FIELDS:
        values = [str(r.get(field) or "").strip() for r in valid if str(r.get(field) or "").strip()]
        if not values:
            continue
        # Prefer Arabic presentation when available; otherwise prefer consensus.
        normalized = {}
        for value in values:
            normalized.setdefault(_norm(value), []).append(value)
        groups = sorted(normalized.values(), key=lambda group: (len(group), _has_arabic(group[0])), reverse=True)
        aggregate[field] = groups[0][0]
        aggregate.setdefault("field_evidence", {})[field] = [
            {"value": r.get(field), "source": r["source"]} for r in valid if r.get(field)]
    aggregate["subjects"] = list(dict.fromkeys(
        subject for r in valid for subject in (r.get("subjects") or []) if subject))[:20]
    # Classification is trusted only when attached to an exact ISBN record.
    if method == "exact_isbn":
        aggregate["ddc"] = next((r.get("ddc") for r in valid if r.get("ddc")), "")
        aggregate["lcc"] = next((r.get("lcc") for r in valid if r.get("lcc")), "")
        aggregate["matched_isbn"] = next((r.get("matched_isbn") for r in valid), "")
    return aggregate


def lookup_book(book):
    """Resolve an exact ISBN, or require two-source title+author consensus."""
    isbn = _isbn(book.get("isbn"))
    if isbn:
        resolvers = (_openlibrary_isbn, _google_books_isbn)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(resolver, isbn) for resolver in resolvers]
            results = []
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception:
                    pass
        return _aggregate(results, "exact_isbn")

    title, author = str(book.get("title") or "").strip(), str(book.get("author") or "").strip()
    if not title or not author:
        return {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_openlibrary_search, title, author),
                   pool.submit(_google_books_search, title, author)]
        candidates = []
        for future in futures:
            try:
                candidates.append(future.result())
            except Exception:
                candidates.append([])
    winners = []
    for source_candidates in candidates:
        score, winner = _best_candidate(source_candidates, book)
        if winner:
            winner["candidate_score"] = score
            winners.append(winner)
    if len(winners) != 2 or _similar(winners[0].get("title"), winners[1].get("title")) < .92:
        return {}
    return _aggregate(winners, "title_author_consensus")


def lookup_isbn(isbn):
    """Backward-compatible exact ISBN lookup."""
    return lookup_book({"isbn": isbn})


def merge_verified(observed_book, verified):
    """Complete missing fields without overwriting stronger photographed evidence."""
    book = dict(observed_book)
    conflicts = list(book.get("verification_conflicts") or [])
    sources = dict(book.get("field_sources") or {})
    confidence = dict(book.get("confidence") or {})
    filled, preserved = [], []
    source_label = " + ".join(verified.get("sources") or [verified.get("source", "مصدر خارجي")])
    exact = (verified.get("match_method") in {"exact_isbn", "web_exact"} or
             (not verified.get("match_method") and
              "isbn" in str(verified.get("source") or "").lower()))
    for field in FIELDS:
        external = str(verified.get(field) or "").strip()
        if not external:
            continue
        observed = str(book.get(field) or "").strip()
        observed_confidence = int(confidence.get(field, 0) or 0)
        different_script = _has_arabic(observed) != _has_arabic(external)
        if observed and _norm(observed) != _norm(external):
            conflicts.append({"field": field, "ocr_value": observed,
                "verified_value": external, "source": source_label,
                "resolution": "preserved_image_value"})
            # Replace only weak OCR, and never replace Arabic with transliteration.
            if observed_confidence >= 75 or (_has_arabic(observed) and different_script):
                preserved.append(field)
                continue
        if not observed or (exact and observed_confidence < 75 and not
                            (_has_arabic(observed) and different_script)):
            book[field] = external
            confidence[field] = 98 if exact else 90
            sources[field] = source_label
            filled.append(field)
    book["verified_subjects"] = verified.get("subjects") or []
    book["verified_ddc"] = verified.get("ddc", "") if exact else ""
    book["verified_lcc"] = verified.get("lcc", "") if exact else ""
    book["verification_source"] = source_label
    book["verification_conflicts"] = conflicts
    book["field_sources"] = sources
    book["confidence"] = confidence
    book["external_match"] = {
        "status": verified.get("match_status", "none"),
        "method": verified.get("match_method", ""),
        "score": verified.get("match_score", 0),
        "sources": verified.get("sources") or [],
        "source_links": verified.get("source_links") or [],
        "match_basis": verified.get("match_basis", ""),
        "filled_fields": filled, "preserved_fields": preserved,
        "message": ("تم إثبات الطبعة بواسطة ISBN مطابق." if exact else
                    "تم إثبات مرشح قوي باتفاق مصدرين؛ يلزم اعتماد بشري."),
    }
    book["external_field_evidence"] = verified.get("field_evidence") or {}
    return book
