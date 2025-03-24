document.addEventListener("DOMContentLoaded", function () {
    const bookTable = document.getElementById("bookTable");
    const addBookButton = document.getElementById("addBookButton");
    
    addBookButton.addEventListener("click", function () {
        const bookTitle = prompt("Enter book title:");
        const bookAuthor = prompt("Enter author name:");
        const bookPrice = prompt("Enter book price:");
        
        if (bookTitle && bookAuthor && bookPrice) {
            addBookToTable(bookTitle, bookAuthor, bookPrice);
        } else {
            alert("All fields are required!");
        }
    });
    
    function addBookToTable(title, author, price) {
        const row = bookTable.insertRow();
        
        row.innerHTML = `
            <td>${title}</td>
            <td>${author}</td>
            <td>${price}</td>
            <td>
                <button class="edit">Edit</button>
                <button class="delete">Delete</button>
            </td>
        `;
        
        row.querySelector(".edit").addEventListener("click", function () {
            editBook(row);
        });
        
        row.querySelector(".delete").addEventListener("click", function () {
            deleteBook(row);
        });
    }
    
    function editBook(row) {
        const newTitle = prompt("Enter new book title:", row.cells[0].textContent);
        const newAuthor = prompt("Enter new author name:", row.cells[1].textContent);
        const newPrice = prompt("Enter new price:", row.cells[2].textContent);
        
        if (newTitle && newAuthor && newPrice) {
            row.cells[0].textContent = newTitle;
            row.cells[1].textContent = newAuthor;
            row.cells[2].textContent = newPrice;
        } else {
            alert("All fields are required!");
        }
    }
    
    function deleteBook(row) {
        if (confirm("Are you sure you want to delete this book?")) {
            row.remove();
        }
    }
});

    