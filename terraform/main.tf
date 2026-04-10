provider "local" {}

resource "local_file" "example" {
  content  = "Hello DevOps Project"
  filename = "output.txt"
}

output "file_path" {
  value = local_file.example.filename
}