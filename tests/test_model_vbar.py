from __future__ import annotations

import gc
import weakref
import unittest
from unittest import mock

from dinkster_aimdo import model_vbar


class FakeVBARLibrary:
    def __init__(self) -> None:
        self.page_counts: list[int] = []
        self.residency_types: list[weakref.ReferenceType[type]] = []

    def vbar_allocate(self, devctx: object, size: int, device: int) -> int:
        return 1

    def vbar_get(self, devctx: object, ptr: int) -> int:
        return 1024

    def vbar_fault(
        self,
        devctx: object,
        ptr: int,
        offset: int,
        size: int,
        signature: object,
    ) -> int:
        return 0

    def vbar_get_nr_pages(self, devctx: object, ptr: int) -> int:
        return self.page_counts.pop(0)

    def vbar_get_residency(
        self,
        devctx: object,
        ptr: int,
        buffer: object,
        nr_pages: int,
    ) -> None:
        self.residency_types.append(weakref.ref(type(buffer)))

    def vbar_free(self, devctx: object, ptr: int) -> None:
        pass


class ModelVBARTypeRetentionTests(unittest.TestCase):
    def make_vbar(self, library: FakeVBARLibrary) -> model_vbar.ModelVBAR:
        with (
            mock.patch.object(model_vbar, "lib", library),
            mock.patch.object(model_vbar.control, "get_devctx", return_value=object()),
        ):
            return model_vbar.ModelVBAR(128 * 1024**2, 0)

    def test_fault_retains_one_type_per_signature_length(self) -> None:
        library = FakeVBARLibrary()
        vbar = self.make_vbar(library)

        with mock.patch.object(model_vbar, "lib", library):
            first = vbar.fault(vbar.base_addr, 1)
            second = vbar.fault(vbar.base_addr, 1)

            self.assertIs(type(first), type(second))
            self.assertIsNot(first, second)

            retained_type = weakref.ref(type(first))
            del first
            del second
            gc.collect()

            third = vbar.fault(vbar.base_addr, 1)

        self.assertIs(retained_type(), type(third))

    def test_residency_type_changes_only_with_page_count(self) -> None:
        library = FakeVBARLibrary()
        library.page_counts = [2, 2, 3]
        vbar = self.make_vbar(library)

        with mock.patch.object(model_vbar, "lib", library):
            self.assertEqual(vbar.get_residency(), [0, 0])
            gc.collect()
            first_type = library.residency_types[-1]
            self.assertIsNotNone(first_type())

            self.assertEqual(vbar.get_residency(), [0, 0])
            gc.collect()
            second_type = library.residency_types[-1]
            self.assertIs(first_type(), second_type())

            self.assertEqual(vbar.get_residency(), [0, 0, 0])
            third_type = library.residency_types[-1]

        self.assertIsNot(second_type(), third_type())


if __name__ == "__main__":
    unittest.main()
