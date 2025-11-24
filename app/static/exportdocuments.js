
    function exportToExcel() {
      const wb = XLSX.utils.book_new();
      const tableIds = ['akelloreportlogo','smartlearning-table','library-mets','library-mets','institutionsTable','studentsByProvinceTabletbl'];

      tableIds.forEach((id, i) => {
        const table = document.getElementById(id);
        const ws = XLSX.utils.table_to_sheet(table);
        XLSX.utils.book_append_sheet(wb, ws, `Sheet${i + 1}`);
      });

      XLSX.writeFile(wb, 'tables_export.xlsx');
    }

    async function exportToPDF() {
      const { jsPDF } = window.jspdf; 
      const doc = new jsPDF();
      const tableIds = ['akelloreportlogo','smartlearning-table','library-mets','library-mets','institutionsTable','studentsByProvinceTabletbl'];

      let y = 10;

      for (let i = 0; i < tableIds.length; i++) {
        const table = document.getElementById(tableIds[i]);
        doc.text(`Table ${i + 1}`, 14, y);
        doc.autoTable({
          html: table,
          startY: y + 5,
          theme: 'striped',
        });
        y = doc.lastAutoTable.finalY + 10;
      }

      doc.save('tables_export.pdf');
    }